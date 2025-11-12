"""Unit tests for scheduler.cli.jobs module"""
import pytest
from unittest.mock import patch, Mock, create_autospec
from datetime import datetime
from scheduler.cli.jobs import jobs_command, _print_job_table, _print_job_details
from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.core import Job
from scheduler.core.config import Config
from scheduler.api import SchedulerClient
from scheduler.api.client import SchedulerClient


class TestJobsCommand:
    """Tests for jobs_command function"""

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_list_jobs_success(self, mock_client_class, mock_load_config):
        """Test listing jobs successfully"""
        # Create a proper mock job with all necessary attributes
        mock_job = Mock(spec_set=Job)
        mock_job.to_dict.return_value = {
            "job_id": "job_123",
            "name": "test",
            "status": "pending"
        }
        mock_job.job_id = "job_123"
        mock_job.name = "test"
        mock_job.status.value = "pending"
        mock_job.assigned_node = None
        mock_job.assigned_gpus = []
        mock_job.started_at = None
        mock_job.completed_at = None
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.list_jobs.return_value = [mock_job]
        mock_client_class.return_value = mock_client
        mock_load_config.return_value = create_autospec(Config, instance=True, spec_set=True)

        with patch('scheduler.cli.jobs.click.echo', autospec=True) as mock_echo:
            result = jobs_command()
            assert result == 0
            mock_client.list_jobs.assert_called_once()

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_list_jobs_with_filter(self, mock_client_class, mock_load_config):
        """Test listing jobs with status filter"""
        mock_job = Mock(spec_set=Job)
        mock_job.to_dict.return_value = {"job_id": "job_123"}
        mock_job.job_id = "job_123"
        mock_job.name = "test"
        mock_job.status.value = "running"
        mock_job.assigned_node = None
        mock_job.assigned_gpus = []
        mock_job.started_at = None
        mock_job.completed_at = None
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.list_jobs.return_value = [mock_job]
        mock_client_class.return_value = mock_client
        mock_load_config.return_value = create_autospec(Config, instance=True, spec_set=True)

        with patch('scheduler.cli.jobs.click.echo', autospec=True):
            result = jobs_command(filter="running", limit=10)
            assert result == 0
            mock_client.list_jobs.assert_called_once_with(status_filter="running", limit=10)

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_get_specific_job_ids(self, mock_client_class, mock_load_config):
        """Test getting specific job IDs"""
        mock_job = Mock(spec_set=Job)
        mock_job.to_dict.return_value = {"job_id": "job_123"}
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.get_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.jobs.click.echo', autospec=True):
            result = jobs_command(job_ids=["job_123", "job_456"])
            assert result == 0
            assert mock_client.get_job.call_count == 2

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_list_jobs_json_format(self, mock_client_class, mock_load_config):
        """Test listing jobs in JSON format"""
        mock_job = Mock(spec_set=Job)
        mock_job.to_dict.return_value = {"job_id": "job_123"}
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.list_jobs.return_value = [mock_job]
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.jobs.click.echo', autospec=True):
            result = jobs_command(format="json")
            assert result == 0

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_list_jobs_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        from scheduler.core.exceptions import ConnectionException
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.list_jobs.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.jobs.click.echo', autospec=True):
            result = jobs_command()
            assert result == 3

    @patch('scheduler.cli.jobs.load_config', autospec=True)
    @patch('scheduler.cli.jobs.SchedulerClient', autospec=True)
    def test_list_jobs_generic_exception(self, mock_client_class, mock_load_config):
        """Test handling generic exception"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.list_jobs.side_effect = Exception("Generic error")
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.jobs.click.echo', autospec=True):
            result = jobs_command()
            assert result == 1


class TestPrintJobTable:
    """Tests for _print_job_table function"""

    def test_print_job_table_empty(self):
        """Test printing empty job list"""
        with patch('scheduler.cli.jobs.click.echo', autospec=True) as mock_echo:
            _print_job_table([])
            mock_echo.assert_called_once_with("No jobs found")

    def test_print_job_table_with_jobs(self):
        """Test printing jobs in table format"""
        jobs = [
            Job(
                job_id="job_123",
                name="test_job",
                script="/path/script.py",
                requirements=JobRequirement("2"),
                status=JobStatus.RUNNING,
                assigned_node="node1",
                assigned_gpus=[0, 1],
                started_at=datetime.now()
            )
        ]
        
        with patch('scheduler.cli.jobs.click.echo', autospec=True) as mock_echo:
            _print_job_table(jobs)
            # Should print header and job row
            assert mock_echo.call_count == 3  # header line, separator line, job row


class TestPrintJobDetails:
    """Tests for _print_job_details function"""

    def test_print_job_details_with_all_fields(self):
        """Test printing job details with all fields"""
        job = Job(
            job_id="job_123",
            name="test_job",
            script="/path/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.COMPLETED,
            assigned_node="node1",
            assigned_gpus=[0, 1],
            exit_code=0,
            error_message="Error occurred"
        )
        
        with patch('scheduler.cli.jobs.click.echo', autospec=True) as mock_echo:
            _print_job_details(job)
            # Should print multiple lines
            assert mock_echo.call_count > 5

    def test_print_job_details_minimal(self):
        """Test printing job details with minimal fields"""
        job = Job(
            job_id="job_123",
            name="test_job",
            script="/path/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        
        with patch('scheduler.cli.jobs.click.echo', autospec=True) as mock_echo:
            _print_job_details(job)
            # Should still print multiple lines
            assert mock_echo.call_count >= 4

