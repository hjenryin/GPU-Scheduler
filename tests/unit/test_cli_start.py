"""Unit tests for scheduler.cli.start module"""
import pytest
import os
import sys
from unittest.mock import Mock, patch, MagicMock
import click

from scheduler.cli.start import start_command, _start_head_node, _start_worker_node
from scheduler.core import Config, ValidationException, ConnectionException, PermissionDeniedException
from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig, ClientConfig


class TestStartCommandValidation:
    """Tests for start_command argument validation"""

    def test_start_without_head_or_address(self):
        """Test starting without --head or --address"""
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=False, address=None)
            assert result == 2

    @patch('scheduler.cli.start.click.echo')
    def test_start_with_both_head_and_address(self, mock_echo):
        """Test starting with both --head and --address (warning)"""
        with patch('scheduler.cli.start.load_config') as mock_load, \
             patch('scheduler.cli.start._start_head_node') as mock_start_head:
            mock_load.return_value = Config()
            mock_start_head.return_value = 0
            
            result = start_command(head=True, address="localhost:9000")
            assert result == 0
            # Should print warning
            mock_echo.assert_called()


class TestStartCommandHeadNode:
    """Tests for starting head node"""

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_node_success(self, mock_start, mock_load):
        """Test starting head node successfully"""
        mock_load.return_value = Config()
        mock_start.return_value = 0
        
        result = start_command(head=True, port=8265)
        assert result == 0
        mock_start.assert_called_once()

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_node_with_kwargs(self, mock_start, mock_load):
        """Test starting head with additional kwargs"""
        mock_load.return_value = Config()
        mock_start.return_value = 0
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(
                head=True,
                port=8265,
                heartbeat_timeout=30,
                scheduling_interval=10
            )
            assert result == 0

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_validation_exception(self, mock_start, mock_load):
        """Test handling ValidationException"""
        mock_load.return_value = Config()
        mock_start.side_effect = ValidationException("Invalid config")
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=True)
            assert result == 2

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_permission_exception(self, mock_start, mock_load):
        """Test handling PermissionDeniedException"""
        mock_load.return_value = Config()
        mock_start.side_effect = PermissionDeniedException("Port in use")
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=True)
            assert result == 5

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_keyboard_interrupt(self, mock_start, mock_load):
        """Test handling KeyboardInterrupt"""
        mock_load.return_value = Config()
        mock_start.side_effect = KeyboardInterrupt()
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=True)
            assert result == 0

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_head_node')
    def test_start_head_generic_exception(self, mock_start, mock_load):
        """Test handling generic exception"""
        mock_load.return_value = Config()
        mock_start.side_effect = Exception("Unexpected error")
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=True)
            assert result == 1


class TestStartCommandWorkerNode:
    """Tests for starting worker node"""

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_worker_node')
    def test_start_worker_node_success(self, mock_start, mock_load):
        """Test starting worker node successfully"""
        mock_load.return_value = Config()
        mock_start.return_value = 0
        
        result = start_command(head=False, address="localhost:9000")
        assert result == 0
        mock_start.assert_called_once()

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_worker_node')
    def test_start_worker_with_kwargs(self, mock_start, mock_load):
        """Test starting worker with additional kwargs"""
        mock_load.return_value = Config()
        mock_start.return_value = 0
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(
                head=False,
                address="localhost:9000",
                gpu_poll_interval=5
            )
            assert result == 0

    @patch('scheduler.cli.start.load_config')
    @patch('scheduler.cli.start._start_worker_node')
    def test_start_worker_connection_exception(self, mock_start, mock_load):
        """Test handling ConnectionException"""
        mock_load.return_value = Config()
        mock_start.side_effect = ConnectionException("Cannot connect")
        
        with patch('scheduler.cli.start.click.echo'):
            result = start_command(head=False, address="localhost:99999")
            assert result == 3


class TestStartHeadNodeImplementation:
    """Tests for _start_head_node implementation"""

    @patch('scheduler.core.utils.is_port_available')
    @patch('scheduler.cli.start.SingletonDaemon')
    @patch('scheduler.cli.start.Orchestrator')
    @patch('scheduler.cli.start._start_worker_node')
    @patch('scheduler.cli.start.click.echo')
    def test_start_head_port_available(self, mock_echo, mock_worker, mock_orch_class, mock_singleton_class, mock_port_check):
        """Test starting head when port is available"""
        mock_port_check.return_value = True
        
        mock_singleton = MagicMock()
        mock_singleton.acquire_lock.return_value = True
        mock_singleton_class.return_value = mock_singleton
        
        mock_orch = MagicMock()
        mock_orch.run.return_value = None
        mock_orch_class.return_value = mock_orch
        
        config = Config(
            head=HeadConfig(port=8265),
            worker=WorkerConfig()
        )
        
        result = _start_head_node(config, block=True)
        assert result == 0

    @patch('scheduler.core.utils.is_port_available')
    @patch('scheduler.core.utils.find_available_port')
    @patch('scheduler.cli.start.click.echo')
    def test_start_head_port_unavailable(self, mock_echo, mock_find_port, mock_port_check):
        """Test starting head when port is unavailable"""
        mock_port_check.return_value = False
        mock_find_port.return_value = 8266
        
        config = Config(
            head=HeadConfig(port=8265),
            worker=WorkerConfig()
        )
        
        with patch('scheduler.cli.start.SingletonDaemon') as mock_singleton_class, \
             patch('scheduler.cli.start.Orchestrator'):
            mock_singleton = MagicMock()
            mock_singleton.acquire_lock.return_value = True
            mock_singleton_class.return_value = mock_singleton
            
            result = _start_head_node(config, block=True)
            assert result == 0


class TestStartWorkerNodeImplementation:
    """Tests for _start_worker_node implementation"""

    @patch('scheduler.core.head_info.save_head_info')
    @patch('scheduler.cli.start.SingletonDaemon')
    @patch('scheduler.cli.start.WorkerDaemon')
    @patch('scheduler.cli.start.click.echo')
    def test_start_worker_success_blocking(self, mock_echo, mock_daemon_class, mock_singleton_class, mock_save_info):
        """Test starting worker in blocking mode"""
        mock_singleton = MagicMock()
        mock_singleton.acquire_lock.return_value = True
        mock_singleton_class.return_value = mock_singleton
        
        mock_daemon = MagicMock()
        mock_daemon.run.return_value = None
        mock_daemon_class.return_value = mock_daemon
        
        config = Config(
            address="localhost:9000",
            worker=WorkerConfig()
        )
        
        result = _start_worker_node(config, node_name="test-node", num_gpus=2, block=True)
        assert result == 0
        mock_save_info.assert_called_once_with("localhost:9000")

    @patch('scheduler.core.head_info.save_head_info')
    @patch('scheduler.cli.start.SingletonDaemon')
    @patch('scheduler.cli.start.WorkerDaemon')
    @patch('scheduler.cli.start.click.echo')
    def test_start_worker_success_background(self, mock_echo, mock_daemon_class, mock_singleton_class, mock_save_info):
        """Test starting worker in background mode"""
        mock_singleton = MagicMock()
        mock_singleton.acquire_lock.return_value = True
        mock_singleton_class.return_value = mock_singleton
        
        mock_daemon = MagicMock()
        mock_daemon_class.return_value = mock_daemon
        
        config = Config(
            address="localhost:9000",
            worker=WorkerConfig()
        )
        
        result = _start_worker_node(config, node_name="test-node", num_gpus=None, block=False)
        assert result == 0
        mock_daemon.start.assert_called_once()

