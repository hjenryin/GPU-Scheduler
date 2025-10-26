"""Unit tests for scheduler.cli.cancel module"""
import pytest
from unittest.mock import patch, Mock
from scheduler.cli.cancel import cancel_command
from scheduler.core.exceptions import ConnectionException, JobNotFoundException


class TestCancelCommand:
    """Tests for cancel_command function"""

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_job_success(self, mock_client_class, mock_load_config):
        """Test successful job cancellation"""
        mock_client = Mock()
        mock_client.cancel_job.return_value = {"status": "cancelled", "job_id": "job_123"}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo') as mock_echo:
            result = cancel_command(["job_123"])
            assert result == 0
            mock_client.cancel_job.assert_called_once_with("job_123")
            mock_echo.assert_called()

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_multiple_jobs(self, mock_client_class, mock_load_config):
        """Test canceling multiple jobs"""
        mock_client = Mock()
        mock_client.cancel_job.return_value = {"status": "cancelled"}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo'):
            result = cancel_command(["job_123", "job_456", "job_789"])
            assert result == 0
            assert mock_client.cancel_job.call_count == 3

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_job_not_found(self, mock_client_class, mock_load_config):
        """Test canceling a non-existent job"""
        mock_client = Mock()
        mock_client.cancel_job.side_effect = JobNotFoundException("Job not found")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo') as mock_echo:
            result = cancel_command(["nonexistent"])
            assert result == 0  # Still returns 0, just prints error message
            mock_echo.assert_called()

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_mixed_results(self, mock_client_class, mock_load_config):
        """Test canceling mix of existing and non-existing jobs"""
        mock_client = Mock()
        
        def cancel_side_effect(job_id):
            if job_id == "job_123":
                return {"status": "cancelled"}
            elif job_id == "job_456":
                raise JobNotFoundException("Job not found")
        
        mock_client.cancel_job.side_effect = cancel_side_effect
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo'):
            result = cancel_command(["job_123", "job_456"])
            assert result == 0  # Partial success still returns 0

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        mock_client = Mock()
        mock_client.cancel_job.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo'):
            result = cancel_command(["job_123"])
            assert result == 3

    @patch('scheduler.cli.cancel.load_config')
    @patch('scheduler.cli.cancel.SchedulerClient')
    def test_cancel_generic_exception(self, mock_client_class, mock_load_config):
        """Test handling generic exception"""
        mock_client = Mock()
        mock_client.cancel_job.side_effect = Exception("Generic error")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.cancel.click.echo'):
            result = cancel_command(["job_123"])
            assert result == 1

