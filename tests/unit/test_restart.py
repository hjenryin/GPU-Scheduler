"""Unit tests for cluster restart plumbing."""
import asyncio
import json
import os
from unittest.mock import create_autospec, patch

from click.testing import CliRunner

from scheduler.api.client import SchedulerClient
from scheduler.api.schemas import HeartbeatResponse
from scheduler.core import RestartState
from scheduler.core.singleton import SingletonDaemon
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.worker.heartbeat import HeartbeatSender


def test_node_manager_restart_ack_and_rejoin(node_manager, sample_gpu_stats):
    node_manager.register_node("gpu1", "192.168.1.10", 2)
    node_manager.update_heartbeat("gpu1", sample_gpu_stats)

    targets = node_manager.request_restart_all_workers("restart-1")

    assert targets == ["gpu1"]
    node = node_manager.get_node("gpu1")
    assert node.restart_state == RestartState.REQUESTED
    assert node.restart_id == "restart-1"

    node_manager.update_heartbeat("gpu1", sample_gpu_stats, restart_acknowledged=True)
    assert node_manager.get_node("gpu1").restart_state == RestartState.ACKNOWLEDGED

    node_manager.register_node("gpu1", "192.168.1.10", 2, restart_id="restart-1")
    assert node_manager.get_node("gpu1").restart_state == RestartState.REJOINED
    progress = node_manager.get_restart_progress("restart-1", ["gpu1"])
    assert progress == {
        "acked_nodes": ["gpu1"],
        "rejoined_nodes": ["gpu1"],
        "missing_nodes": [],
    }


def test_heartbeat_sender_acknowledges_restart(test_config):
    gpu_monitor = create_autospec(GPUMonitor, instance=True, spec_set=True)
    gpu_monitor.get_latest_stats.return_value = []

    client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    client.send_heartbeat.return_value = HeartbeatResponse(
        status="ok",
        shutdown_requested=False,
        restart_requested=True,
        restart_id="restart-1",
    )

    with patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True, return_value=client):
        sender = HeartbeatSender("gpu1", "localhost:8266", gpu_monitor, test_config)
        stop_requested = sender.send_heartbeat()

    assert stop_requested is True
    assert sender.is_restart_requested() is True
    assert sender.restart_id == "restart-1"
    assert client.send_heartbeat.call_count == 2
    assert client.send_heartbeat.call_args_list[1].kwargs["restart_acknowledged"] is True


def test_singleton_adopts_same_pid_lock(temp_dir):
    lock_path = os.path.join(temp_dir, "worker.lock")
    with open(lock_path, "w") as f:
        json.dump({"pid": os.getpid()}, f)

    singleton = SingletonDaemon(lock_path)

    assert singleton.acquire_lock() is True
    singleton.release_lock()
    assert not os.path.exists(lock_path)


def test_cli_routes_restart_command():
    from scheduler.cli.main import cli

    runner = CliRunner()
    with patch('scheduler.cli.main.restart_command', autospec=True, return_value=0) as restart_command:
        result = runner.invoke(cli, ['restart', '--timeout', '7'])

    assert result.exit_code == 0
    restart_command.assert_called_once_with(timeout=7)


def test_restart_cluster_route_calls_orchestrator():
    from scheduler.api.routes import restart_cluster_route
    from scheduler.head.orchestrator import Orchestrator

    orchestrator = create_autospec(Orchestrator, instance=True, spec_set=True)
    orchestrator.restart_cluster.return_value = {
        "status": "restart_scheduled",
        "restart_id": "restart-1",
        "acked_nodes": [],
        "rejoined_nodes": [],
        "missing_nodes": [],
        "head_restart_scheduled": True,
    }

    with patch('scheduler.head.Orchestrator.get_instance', autospec=True, return_value=orchestrator):
        result = asyncio.run(restart_cluster_route(timeout=3))

    assert result["status"] == "restart_scheduled"
    orchestrator.restart_cluster.assert_called_once_with(3)
