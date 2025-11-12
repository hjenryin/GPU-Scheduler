"""
Comprehensive tests for cli/stop.py to improve coverage to 90%+
"""
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open, create_autospec
from click.testing import CliRunner

from scheduler.cli.stop import (
    stop_command,
    _stop_all_nodes,
    _is_running_on_head_node,
    _stop_local_worker_nodes,
    _stop_daemon
)
from scheduler.core import ConnectionException
from scheduler.api.client import SchedulerClient
from scheduler.core.models import Node


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
@patch('scheduler.cli.stop.os.listdir', autospec=True)
def test_stop_command_no_workers_found(mock_listdir, mock_exists, mock_is_daemon):
    """Test stop_command when no workers are running"""
    mock_exists.return_value = True
    mock_listdir.return_value = []
    mock_is_daemon.return_value = False
    
    result = stop_command(all_nodes=False)
    assert result == 1


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
@patch('scheduler.cli.stop.os.listdir', autospec=True)
@patch('scheduler.cli.stop._stop_daemon', autospec=True)
def test_stop_command_with_head_warning(mock_stop_daemon, mock_listdir, mock_exists, mock_is_daemon):
    """Test stop_command shows warning when head is still running"""
    mock_exists.return_value = True
    mock_listdir.return_value = ['worker-node1.lock']
    mock_is_daemon.return_value = True  # Head is running
    mock_stop_daemon.return_value = True
    
    result = stop_command(all_nodes=False)
    assert result == 0
    mock_stop_daemon.assert_called_once()


@patch('scheduler.cli.stop._stop_all_nodes', autospec=True)
def test_stop_command_all_nodes(mock_stop_all):
    """Test stop_command with all_nodes=True"""
    mock_stop_all.return_value = 0
    
    result = stop_command(all_nodes=True)
    assert result == 0
    mock_stop_all.assert_called_once()


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
@patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
def test_stop_all_nodes_from_head_success(mock_exists, mock_stop_local, mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when running from head node - successful API call"""
    mock_is_head.return_value = True
    mock_exists.return_value = True

    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.return_value = [create_autospec(Node, instance=True, spec_set=True), create_autospec(Node, instance=True, spec_set=True)]
    mock_client.shutdown_cluster.return_value = True
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 0
    mock_client.shutdown_cluster.assert_called_once()


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
@patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
def test_stop_all_nodes_from_head_api_fails(mock_stop_local, mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when API call fails, falls back to local stop"""
    mock_is_head.return_value = True
    mock_stop_local.return_value = True

    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.shutdown_cluster.side_effect = Exception("API error")
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 0
    mock_stop_local.assert_called()


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_from_worker_success(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when running from worker node"""
    mock_is_head.return_value = False
    
    mock_node1 = create_autospec(Node, instance=True, spec_set=True)
    mock_node1.node_name = "node1"
    mock_node1.address = "localhost:5001"
    mock_node1.status.value = "connected"
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.return_value = [mock_node1]
    mock_client.shutdown_cluster.return_value = True
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 0
    mock_client.shutdown_cluster.assert_called_once()


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_from_worker_no_nodes(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when no nodes are found"""
    mock_is_head.return_value = False
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.return_value = []
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 1


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_connection_exception(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when ConnectionException is raised"""
    mock_is_head.return_value = False
    mock_client_class.side_effect = ConnectionException("Cannot connect")
    
    result = _stop_all_nodes()
    assert result == 1


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_generic_exception(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when generic exception is raised"""
    mock_is_head.return_value = False
    mock_client_class.side_effect = RuntimeError("Unexpected error")
    
    result = _stop_all_nodes()
    assert result == 1


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
def test_is_running_on_head_node_true(mock_exists, mock_is_daemon):
    """Test _is_running_on_head_node returns True when head is running"""
    mock_exists.return_value = True
    mock_is_daemon.return_value = True
    
    result = _is_running_on_head_node()
    assert result is True


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
def test_is_running_on_head_node_false(mock_exists, mock_is_daemon):
    """Test _is_running_on_head_node returns False when head is not running"""
    mock_exists.return_value = False
    
    result = _is_running_on_head_node()
    assert result is False


@patch('scheduler.cli.stop.os.path.exists', autospec=True)
@patch('scheduler.cli.stop.os.listdir', autospec=True)
@patch('scheduler.cli.stop._stop_daemon', autospec=True)
def test_stop_local_worker_nodes_success(mock_stop_daemon, mock_listdir, mock_exists):
    """Test _stop_local_worker_nodes stops workers successfully"""
    mock_exists.return_value = True
    mock_listdir.return_value = ['worker-node1.lock', 'worker-node2.lock', 'head.lock']
    mock_stop_daemon.return_value = True
    
    result = _stop_local_worker_nodes()
    assert result is True
    assert mock_stop_daemon.call_count == 2


@patch('scheduler.cli.stop.os.path.exists', autospec=True)
def test_stop_local_worker_nodes_no_dir(mock_exists):
    """Test _stop_local_worker_nodes when scheduler dir doesn't exist"""
    mock_exists.return_value = False
    
    result = _stop_local_worker_nodes()
    assert result is False


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
def test_stop_daemon_not_running(mock_is_daemon):
    """Test _stop_daemon when daemon is not running"""
    mock_is_daemon.return_value = False
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is False


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"pid": 12345}')
@patch('scheduler.cli.stop.os.kill')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_success(mock_remove, mock_kill, mock_file, mock_is_daemon):
    """Test _stop_daemon successfully stops a daemon"""
    mock_is_daemon.return_value = True
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is True
    mock_kill.assert_called_once_with(12345, os.kill.__wrapped__.__defaults__[0] if hasattr(os.kill, '__wrapped__') else 15)


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"no_pid": 12345}')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_no_pid_in_lockfile(mock_remove, mock_file, mock_is_daemon):
    """Test _stop_daemon when lockfile has no PID"""
    mock_is_daemon.return_value = True
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is False


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='invalid json')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_invalid_json(mock_remove, mock_file, mock_is_daemon):
    """Test _stop_daemon when lockfile has invalid JSON"""
    mock_is_daemon.return_value = True
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is False
    mock_remove.assert_called_once()


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"pid": 12345}')
@patch('scheduler.cli.stop.os.kill')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_process_lookup_error(mock_remove, mock_kill, mock_file, mock_is_daemon):
    """Test _stop_daemon when process doesn't exist"""
    mock_is_daemon.return_value = True
    mock_kill.side_effect = ProcessLookupError("Process not found")
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is False
    mock_remove.assert_called_once()


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"pid": 12345}')
@patch('scheduler.cli.stop.os.kill')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_permission_error(mock_remove, mock_kill, mock_file, mock_is_daemon):
    """Test _stop_daemon when permission denied"""
    mock_is_daemon.return_value = True
    mock_kill.side_effect = PermissionError("Permission denied")
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is False


@patch('scheduler.cli.stop.is_daemon_running', autospec=True)
@patch('builtins.open', new_callable=mock_open, read_data='{"pid": 12345}')
@patch('scheduler.cli.stop.os.kill')
@patch('scheduler.cli.stop.os.remove')
def test_stop_daemon_lockfile_remove_fails(mock_remove, mock_kill, mock_file, mock_is_daemon):
    """Test _stop_daemon when lockfile removal fails"""
    mock_is_daemon.return_value = True
    mock_remove.side_effect = OSError("Cannot remove file")
    
    result = _stop_daemon("/tmp/test.lock", "test daemon")
    assert result is True  # Daemon was stopped even if lockfile removal failed


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_from_worker_shutdown_fails(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when shutdown_cluster returns False"""
    mock_is_head.return_value = False
    
    mock_node1 = create_autospec(Node, instance=True, spec_set=True)
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.return_value = [mock_node1]
    mock_client.shutdown_cluster.return_value = False
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 1


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
def test_stop_all_nodes_from_worker_connection_exception_on_shutdown(mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when ConnectionException during shutdown"""
    mock_is_head.return_value = False
    
    mock_node1 = create_autospec(Node, instance=True, spec_set=True)
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.return_value = [mock_node1]
    mock_client.shutdown_cluster.side_effect = ConnectionException("Connection lost")
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 1


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
@patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
def test_stop_all_nodes_from_head_list_nodes_fails(mock_stop_local, mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when list_nodes fails but shutdown continues"""
    mock_is_head.return_value = True
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.list_nodes.side_effect = Exception("Cannot list nodes")
    mock_client.shutdown_cluster.return_value = True
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 0


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
@patch('scheduler.cli.stop.SchedulerClient', autospec=True)
@patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
@patch('scheduler.cli.stop.os.path.exists', autospec=True)
def test_stop_all_nodes_from_head_no_lockfile(mock_exists, mock_stop_local, mock_client_class, mock_load_config, mock_is_head):
    """Test _stop_all_nodes when head lockfile doesn't exist after shutdown"""
    mock_is_head.return_value = True
    mock_exists.return_value = False
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.shutdown_cluster.return_value = True
    mock_client_class.return_value = mock_client
    
    result = _stop_all_nodes()
    assert result == 0


@patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
@patch('scheduler.cli.stop.load_config', autospec=True)
def test_stop_all_nodes_from_head_cannot_connect(mock_load_config, mock_is_head):
    """Test _stop_all_nodes when cannot connect to API from head node"""
    mock_is_head.return_value = True
    mock_load_config.side_effect = Exception("Cannot load config")
    
    result = _stop_all_nodes()
    assert result == 0  # Still succeeds with fallback
