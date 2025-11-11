"""Unit tests for scheduler.cli.logs module"""
import pytest
from unittest.mock import patch, Mock
from scheduler.cli.logs import logs_command
from scheduler.core.exceptions import ConnectionException, JobNotFoundException
from scheduler.api import SchedulerClient
from scheduler.api.client import SchedulerClient


class TestLogsCommand:
    """Tests for logs_command function"""

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_get_job_logs_success(self, mock_client_class, mock_load_config):
        """Test successfully getting job logs"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.return_value = "log content here"
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True) as mock_echo:
            result = logs_command("job_123", lines=50)
            assert result == 0
            mock_client.get_job_logs.assert_called_once_with("job_123", lines=50, stderr=False)
            mock_echo.assert_called_once_with("log content here")

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_get_stderr_logs(self, mock_client_class, mock_load_config):
        """Test getting stderr logs"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.return_value = "error log content"
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True):
            result = logs_command("job_123", stderr=True)
            assert result == 0
            mock_client.get_job_logs.assert_called_once_with("job_123", lines=100, stderr=True)

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_get_both_logs(self, mock_client_class, mock_load_config):
        """Test getting both stdout and stderr logs"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.side_effect = ["stdout content", "stderr content"]
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True) as mock_echo:
            result = logs_command("job_123", both=True)
            assert result == 0
            assert mock_echo.call_count >= 3  # Header, stdout, header, stderr

    @pytest.mark.skip(reason="Streaming/follow mode not implemented in current version")
    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_stream_logs(self, mock_client_class, mock_load_config):
        """Test streaming job logs with follow mode"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.stream_job_logs.return_value = ["line1", "line2", "line3"]
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True) as mock_echo:
            result = logs_command("job_123", follow=True)
            assert result == 0
            mock_client.stream_job_logs.assert_called_once_with("job_123", stderr=False)

    @pytest.mark.skip(reason="Streaming/follow mode not implemented in current version")
    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_stream_logs_keyboard_interrupt(self, mock_client_class, mock_load_config):
        """Test handling KeyboardInterrupt when streaming logs"""
        def stream_side_effect(*args, **kwargs):
            raise KeyboardInterrupt()
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.stream_job_logs.side_effect = stream_side_effect
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True) as mock_echo:
            result = logs_command("job_123", follow=True)
            assert result == 0
            mock_echo.assert_called()

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_job_not_found(self, mock_client_class, mock_load_config):
        """Test handling JobNotFoundException"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.side_effect = JobNotFoundException("Job not found")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True):
            result = logs_command("nonexistent")
            assert result == 4

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True):
            result = logs_command("job_123")
            assert result == 3

    @patch('scheduler.cli.logs.load_config', autospec=True)
    @patch('scheduler.cli.logs.SchedulerClient', autospec=True)
    def test_generic_exception(self, mock_client_class, mock_load_config):
        """Test handling generic exception"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job_logs.side_effect = Exception("Generic error")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.logs.click.echo', autospec=True):
            result = logs_command("job_123")
            assert result == 1

