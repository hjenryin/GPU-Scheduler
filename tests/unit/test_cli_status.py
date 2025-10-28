"""Unit tests for scheduler.cli.status module"""
import pytest
from unittest.mock import patch, Mock, create_autospec
from scheduler.cli.status import status_command
from scheduler.core import Config
from scheduler.core.config import HeadConfig
from scheduler.api import SchedulerClient
from scheduler.api.client import SchedulerClient


class TestStatusCommand:
    """Tests for status_command function"""

    @patch('scheduler.cli.status.load_config', autospec=True)
    @patch('scheduler.cli.status.SchedulerClient', autospec=True)
    @patch('scheduler.cli.status.run_tui', autospec=True)
    def test_status_success(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test successful TUI launch"""
        config = Config(
            address="localhost:8265",
            head=HeadConfig(port=8265)
        )
        mock_load_config.return_value = config
        
        mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client.list_nodes.return_value = []
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo', autospec=True):
            result = status_command()
            assert result == 0
            mock_run_tui.assert_called_once()

    @patch('scheduler.cli.status.load_config', autospec=True)
    @patch('scheduler.cli.status.SchedulerClient', autospec=True)
    def test_status_connection_error(self, mock_client_class, mock_load_config):
        """Test handling connection error"""
        config = Config(
            address="localhost:8265",
            head=HeadConfig(port=8265)
        )
        mock_load_config.return_value = config
        
        mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client.list_nodes.side_effect = Exception("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo', autospec=True) as mock_echo:
            result = status_command()
            assert result == 1
            mock_echo.assert_called()

    @patch('scheduler.cli.status.load_config', autospec=True)
    @patch('scheduler.cli.status.SchedulerClient', autospec=True)
    @patch('scheduler.cli.status.run_tui', autospec=True)
    def test_status_keyboard_interrupt(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test handling KeyboardInterrupt"""
        config = Config(
            address="localhost:8265",
            head=HeadConfig(port=8265)
        )
        mock_load_config.return_value = config
        
        mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client.list_nodes.return_value = []
        mock_run_tui.side_effect = KeyboardInterrupt()
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo', autospec=True) as mock_echo:
            result = status_command()
            assert result == 0
            mock_echo.assert_called_with("\nExiting...")

    @patch('scheduler.cli.status.load_config', autospec=True)
    @patch('scheduler.cli.status.SchedulerClient', autospec=True)
    @patch('scheduler.cli.status.run_tui', autospec=True)
    def test_status_generic_exception(self, mock_run_tui, mock_client_class, mock_load_config):
        """Test handling generic exception"""
        config = Config(
            address="localhost:8265",
            head=HeadConfig(port=8265)
        )
        mock_load_config.return_value = config
        
        mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client.list_nodes.return_value = []
        mock_run_tui.side_effect = Exception("TUI error")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.status.click.echo', autospec=True):
            result = status_command()
            assert result == 1

    @patch('scheduler.cli.status.load_config', autospec=True)
    def test_status_no_address_config(self, mock_load_config):
        """Test TUI with no address in config"""
        config = Config(
            address=None,
            head=HeadConfig(port=8265)
        )
        mock_load_config.return_value = config
        
        with patch('scheduler.cli.status.SchedulerClient', autospec=True) as mock_client_class, \
             patch('scheduler.cli.status.run_tui', autospec=True) as mock_run_tui:
            mock_client = Mock(spec_set=SchedulerClient)
            mock_client.list_nodes.return_value = []
            mock_client_class.return_value = mock_client

            with patch('scheduler.cli.status.click.echo', autospec=True):
                result = status_command()
                assert result == 0
                # Should construct address from head.port
                mock_client_class.assert_called_once()

