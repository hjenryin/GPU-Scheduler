"""Unit tests for scheduler.cli.stop module"""
import pytest
import os
import json
import signal
from unittest.mock import Mock, patch, MagicMock, mock_open
import click

from scheduler.cli.stop import (
    stop_command,
    _stop_all_nodes,
    _is_running_on_head_node,
    _stop_local_worker_nodes,
    _stop_daemon
)
from scheduler.core.exceptions import ConnectionException


class TestStopCommand:
    """Tests for stop_command function"""

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    @patch('scheduler.cli.stop._stop_daemon', autospec=True)
    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    @patch('scheduler.cli.stop.os.listdir', autospec=True)
    def test_stop_worker_success(self, mock_listdir, mock_exists, mock_stop_daemon, mock_is_running):
        """Test stopping worker successfully"""
        mock_is_running.return_value = False
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        mock_stop_daemon.return_value = True
        
        with patch('scheduler.cli.stop.click.echo', autospec=True):
            result = stop_command(all_nodes=False)
            assert result == 0

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    def test_stop_no_workers_running(self, mock_is_running):
        """Test stopping when no workers are running"""
        mock_is_running.return_value = False
        
        with patch('scheduler.cli.stop.os.path.exists', return_value=False, autospec=True), \
             patch('scheduler.cli.stop.click.echo', autospec=True) as mock_echo:
            result = stop_command(all_nodes=False)
            assert result == 1
            mock_echo.assert_called_with("No worker processes found running on this machine")

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    @patch('scheduler.cli.stop._stop_daemon', autospec=True)
    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    @patch('scheduler.cli.stop.os.listdir', autospec=True)
    def test_stop_warns_about_head(self, mock_listdir, mock_exists, mock_stop_daemon, mock_is_running):
        """Test stopping worker when head is also running"""
        mock_is_running.side_effect = lambda f: 'head.lock' in f
        
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        mock_stop_daemon.return_value = True
        
        with patch('scheduler.cli.stop.click.echo', autospec=True) as mock_echo:
            result = stop_command(all_nodes=False)
            assert result == 0
            # Should warn about head still running
            assert any("Warning" in str(call) for call in mock_echo.call_args_list)


class TestStopAllNodes:
    """Tests for _stop_all_nodes function"""

    @patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
    @patch('scheduler.cli.stop.load_config', autospec=True)
    @patch('scheduler.cli.stop.SchedulerClient', autospec=True)
    @patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    def test_stop_all_from_head_node(self, mock_exists, mock_stop_local, mock_client_class, mock_load, mock_is_head):
        """Test stopping all nodes when running from head"""
        from scheduler.core.config import Config
        mock_is_head.return_value = True
        mock_load.return_value = Config()
        mock_stop_local.return_value = True
        mock_exists.return_value = True  # Head lock file exists
        
        # Mock the client
        mock_client = MagicMock()
        mock_client.list_nodes.return_value = []
        mock_client.shutdown_cluster.return_value = True
        mock_client_class.return_value = mock_client
        
        with patch('scheduler.cli.stop.click.echo', autospec=True), \
             patch('scheduler.cli.stop.time.sleep', autospec=True):
            result = _stop_all_nodes()
            assert result == 0
            mock_client.shutdown_cluster.assert_called_once()

    @patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
    @patch('scheduler.cli.stop.load_config', autospec=True)
    @patch('scheduler.cli.stop.SchedulerClient', autospec=True)
    @patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
    def test_stop_all_from_worker_node(self, mock_stop_local, mock_client_class, mock_load, mock_is_head):
        """Test stopping all nodes when running from worker"""
        mock_is_head.return_value = False
        
        mock_config = MagicMock()
        mock_config.address = "localhost:9000"
        mock_config.head.port = 9000
        mock_load.return_value = mock_config
        
        mock_client = MagicMock()
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.shutdown_cluster.return_value = True
        mock_client_class.return_value = mock_client
        
        mock_stop_local.return_value = True
        
        with patch('scheduler.cli.stop.click.echo', autospec=True), \
             patch('scheduler.cli.stop.time.sleep', autospec=True):
            result = _stop_all_nodes()
            assert result == 0
            mock_client.shutdown_cluster.assert_called_once()
            # Worker no longer manually stops itself - it stops via heartbeat
            mock_stop_local.assert_not_called()

    @patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
    @patch('scheduler.cli.stop.load_config', autospec=True)
    @patch('scheduler.cli.stop.SchedulerClient', autospec=True)
    @patch('scheduler.cli.stop._stop_local_worker_nodes', autospec=True)
    def test_stop_all_uses_client_auto_detection(self, mock_stop_local, mock_client_class, mock_load, mock_is_head):
        """Test that stop --all uses SchedulerClient's auto-detection"""
        mock_is_head.return_value = False
        
        mock_config = MagicMock()
        mock_config.address = "configured:9000"
        mock_config.head.port = 9000
        mock_load.return_value = mock_config
        
        mock_client = MagicMock()
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.shutdown_cluster.return_value = True
        mock_client_class.return_value = mock_client
        
        mock_stop_local.return_value = True
        
        with patch('scheduler.cli.stop.click.echo', autospec=True):
            result = _stop_all_nodes()
            assert result == 0
            # Should call SchedulerClient with config only (no address)
            # to allow auto-detection from worker lock file
            mock_client_class.assert_called_once_with(config=mock_config)

    @patch('scheduler.cli.stop._is_running_on_head_node', autospec=True)
    @patch('scheduler.cli.stop.load_config', autospec=True)
    @patch('scheduler.cli.stop.SchedulerClient', autospec=True)
    def test_stop_all_connection_exception(self, mock_client_class, mock_load, mock_is_head):
        """Test handling connection exception when stopping all nodes"""
        mock_is_head.return_value = False
        
        mock_config = MagicMock()
        mock_config.address = "localhost:99999"
        mock_config.head.port = 99999
        mock_load.return_value = mock_config
        
        mock_client = MagicMock()
        mock_client.list_nodes.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client
        
        with patch('scheduler.cli.stop.click.echo', autospec=True):
            result = _stop_all_nodes()
            assert result == 1


class TestIsRunningOnHeadNode:
    """Tests for _is_running_on_head_node function"""

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    def test_is_running_on_head_node_true(self, mock_exists, mock_is_running):
        """Test detecting when running on head node"""
        mock_exists.return_value = True
        mock_is_running.return_value = True
        
        result = _is_running_on_head_node()
        assert result is True

    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    def test_is_running_on_head_node_false(self, mock_exists):
        """Test detecting when not running on head node"""
        mock_exists.return_value = False
        
        result = _is_running_on_head_node()
        assert result is False


class TestStopLocalWorkerNodes:
    """Tests for _stop_local_worker_nodes function"""

    @patch('scheduler.cli.stop._stop_daemon', autospec=True)
    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    @patch('scheduler.cli.stop.os.listdir', autospec=True)
    def test_stop_local_workers_success(self, mock_listdir, mock_exists, mock_stop_daemon):
        """Test stopping local worker nodes successfully"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock', 'worker-node2.lock']
        mock_stop_daemon.return_value = True
        
        result = _stop_local_worker_nodes()
        assert result is True
        assert mock_stop_daemon.call_count == 2

    @patch('scheduler.cli.stop.os.path.exists', autospec=True)
    def test_stop_local_workers_none_running(self, mock_exists):
        """Test stopping local workers when none are running"""
        mock_exists.return_value = False
        
        result = _stop_local_worker_nodes()
        assert result is False


class TestStopDaemon:
    """Tests for _stop_daemon function"""

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    def test_stop_daemon_not_running(self, mock_is_running):
        """Test stopping daemon when not running"""
        mock_is_running.return_value = False
        
        result = _stop_daemon("/tmp/test.lock", "test daemon")
        assert result is False

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    @patch('scheduler.cli.stop.os.kill', autospec=True)
    @patch('scheduler.cli.stop.os.remove', autospec=True)
    def test_stop_daemon_success(self, mock_remove, mock_kill, mock_is_running):
        """Test stopping daemon successfully"""
        mock_is_running.return_value = True
        
        mock_data = '{"pid": 12345}'
        
        with patch('builtins.open', mock_open(read_data=mock_data)), \
             patch('scheduler.cli.stop.click.echo', autospec=True):
            result = _stop_daemon("/tmp/test.lock", "test daemon")
            assert result is True
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    @patch('scheduler.cli.stop.os.remove', autospec=True)
    def test_stop_daemon_invalid_lockfile(self, mock_remove, mock_is_running):
        """Test handling invalid lockfile"""
        mock_is_running.return_value = True
        
        mock_data = 'invalid json'
        
        with patch('builtins.open', mock_open(read_data=mock_data)), \
             patch('scheduler.cli.stop.click.echo', autospec=True):
            result = _stop_daemon("/tmp/test.lock", "test daemon")
            assert result is False

    @patch('scheduler.cli.stop.is_daemon_running', autospec=True)
    def test_stop_daemon_handles_process_lookup_error(self, mock_is_running):
        """Test handling ProcessLookupError"""
        mock_is_running.return_value = True
        
        mock_data = '{"pid": 99999}'
        
        with patch('builtins.open', mock_open(read_data=mock_data)), \
             patch('scheduler.cli.stop.os.kill', side_effect=ProcessLookupError(), autospec=True), \
             patch('scheduler.cli.stop.os.remove', autospec=True), \
             patch('scheduler.cli.stop.click.echo', autospec=True) as mock_echo:
            result = _stop_daemon("/tmp/test.lock", "test daemon")
            assert result is False

