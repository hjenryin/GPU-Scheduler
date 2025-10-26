"""Unit tests for scheduler.cli.status module"""
import pytest
from unittest.mock import patch, Mock
from scheduler.cli.status import status_command


class TestStatusCommand:
    """Tests for status_command function"""

    @patch('scheduler.cli.status.load_config')
    @patch('scheduler.cli.status.SchedulerClient')
    @patch('scheduler.cli.status.run_tui')
    def test_status_success(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test successful TUI launch"""
        mock_config = Mock()
        mock_config.address = "localhost:8265"
        mock_config.head.port = 8265
        mock_load_config.return_value = mock_config
        
        mock_client = Mock()
        mock_client.list_nodes.return_value = []
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo'):
            result = status_command()
            assert result == 0
            mock_run_tui.assert_called_once()

    @patch('scheduler.cli.status.load_config')
    @patch('scheduler.cli.status.SchedulerClient')
    def test_status_connection_error(self, mock_client_class, mock_load_config):
        """Test handling connection error"""
        mock_config = Mock()
        mock_config.address = "localhost:8265"
        mock_config.head.port = 8265
        mock_load_config.return_value = mock_config
        
        mock_client = Mock()
        mock_client.list_nodes.side_effect = Exception("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo') as mock_echo:
            result = status_command()
            assert result == 1
            mock_echo.assert_called()

    @patch('scheduler.cli.status.load_config')
    @patch('scheduler.cli.status.SchedulerClient')
    @patch('scheduler.cli.status.run_tui')
    def test_status_keyboard_interrupt(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test handling KeyboardInterrupt"""
        mock_config = Mock()
        mock_config.address = "localhost:8265"
        mock_config.head.port = 8265
        mock_load_config.return_value = mock_config
        
        mock_client = Mock()
        mock_client.list_nodes.return_value = []
        mock_run_tui.side_effect = KeyboardInterrupt()
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo') as mock_echo:
            result = status_command()
            assert result == 0
            mock_echo.assert_called_with("\nExiting...")

    @patch('scheduler.cli.status.load_config')
    @patch('scheduler.cli.status.SchedulerClient')
    @patch('scheduler.cli.status.run_tui')
    def test_status_generic_exception(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test handling generic exception"""
        mock_config = Mock()
        mock_config.address = "localhost:8265"
        mock_config.head.port = 8265
        mock_load_config.return_value = mock_config
        
        mock_client = Mock()
        mock_client.list_nodes.return_value = []
        mock_run_tui.side_effect = Exception("TUI error")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo'):
            result = status_command()
            assert result == 1

    @patch('scheduler.cli.status.load_config')
    def test_status_no_address_config(self, mock_load_config):
        """Test TUI with no address in config"""
        mock_config = Mock()
        mock_config.address = None
        mock_config.head.port = 8265
        mock_load_config.return_value = mock_config
        
        with patch('scheduler.cli.status.SchedulerClient') as mock_client_class, \
             patch('scheduler.cli.status.run_tui') as mock_run_tui:
            mock_client = Mock()
            mock_client.list_nodes.return_value = []
            mock_client_class.return_value = mock_client

            with patch('scheduler.cli.status.click.echo'):
                result = status_command()
                assert result == 0
                # Should construct address from head.port
                mock_client_class.assert_called_once()

