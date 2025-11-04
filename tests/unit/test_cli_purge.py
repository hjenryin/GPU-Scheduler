"""Unit tests for scheduler.cli.purge module"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
from scheduler.cli.purge import purge_command
from scheduler.core.exceptions import ConnectionException, JobNotFoundException, ValidationException
from scheduler.api import SchedulerClient


class TestPurgeCommand:
    """Tests for purge_command function"""

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_by_time_duration(self, mock_client_class, mock_load_config):
        """Test purging jobs by time duration"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_jobs.return_value = {"purged_count": 5}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True) as mock_echo:
            result = purge_command("7d")
            assert result == 0
            mock_client.purge_jobs.assert_called_once()
            
            # Check that before_time was passed
            call_args = mock_client.purge_jobs.call_args
            assert 'before_time' in call_args.kwargs
            assert 'status_filter' in call_args.kwargs
            assert call_args.kwargs['status_filter'] == ['failed', 'completed', 'cancelled']

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_by_time_with_failed_flag(self, mock_client_class, mock_load_config):
        """Test purging only failed jobs by time"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_jobs.return_value = {"purged_count": 3}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True):
            result = purge_command("3w", failed=True)
            assert result == 0
            
            call_args = mock_client.purge_jobs.call_args
            assert call_args.kwargs['status_filter'] == ['failed']

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_by_time_with_multiple_flags(self, mock_client_class, mock_load_config):
        """Test purging with multiple status flags"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_jobs.return_value = {"purged_count": 2}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True):
            result = purge_command("24h", failed=True, completed=True)
            assert result == 0
            
            call_args = mock_client.purge_jobs.call_args
            assert set(call_args.kwargs['status_filter']) == {'failed', 'completed'}

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_by_job_id(self, mock_client_class, mock_load_config):
        """Test purging a specific job by ID"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_job.return_value = {"status": "purge_initiated"}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True) as mock_echo:
            result = purge_command("job_abc123")
            assert result == 0
            mock_client.purge_job.assert_called_once_with("job_abc123")

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_job_not_found(self, mock_client_class, mock_load_config):
        """Test purging a non-existent job"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_job.side_effect = JobNotFoundException("Job not found")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True) as mock_echo:
            result = purge_command("nonexistent_job")
            assert result == 1
            mock_echo.assert_called()

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_jobs.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True):
            result = purge_command("7d")
            assert result == 3

    @patch('scheduler.cli.purge.load_config', autospec=True)
    @patch('scheduler.cli.purge.SchedulerClient', autospec=True)
    def test_purge_zero_jobs(self, mock_client_class, mock_load_config):
        """Test when no jobs match purge criteria"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.purge_jobs.return_value = {"purged_count": 0}
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.purge.click.echo', autospec=True) as mock_echo:
            result = purge_command("7d")
            assert result == 0
            # Check that "No jobs found" message was printed
            echo_calls = [str(call) for call in mock_echo.call_args_list]
            assert any('No jobs found' in str(call) for call in echo_calls)

    def test_time_duration_parsing(self):
        """Test various time duration formats"""
        from scheduler.core import parse_time_duration
        
        # Test valid formats
        assert parse_time_duration("7d") == timedelta(days=7)
        assert parse_time_duration("3w") == timedelta(weeks=3)
        assert parse_time_duration("24h") == timedelta(hours=24)
        assert parse_time_duration("30m") == timedelta(minutes=30)
        assert parse_time_duration("60s") == timedelta(seconds=60)
        
        # Test invalid formats
        with pytest.raises(ValidationException):
            parse_time_duration("7x")  # Invalid unit
        
        with pytest.raises(ValidationException):
            parse_time_duration("abc")  # No number
        
        with pytest.raises(ValidationException):
            parse_time_duration("")  # Empty string
