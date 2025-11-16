"""Unit tests for scheduler.cli.submit module"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
from scheduler.cli.submit import submit_command
from scheduler.api import SchedulerClient
from scheduler.core.exceptions import ValidationException, ConnectionException
from scheduler.core import Job
from scheduler.api.client import SchedulerClient


class TestSubmitCommand:
    """Tests for submit_command function"""

    def test_submit_empty_command(self):
        """Test submitting with empty command"""
        result = submit_command(
            command=[],
            req="1"
        )
        assert result == 4

    def test_submit_invalid_env_var_format(self):
        """Test submitting with invalid environment variable format"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            result = submit_command(
                command=["python", temp_script],
                env=["INVALID_FORMAT_NO_EQUALS"]
            )
            assert result == 2
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_success(self, mock_client_class, mock_load_config):
        """Test successful job submission"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                # Default is async mode ()
                result = submit_command(
                    command=["python", temp_script],
                    req="2",
                    name="test_job"
                )
                assert result == 0
                mock_client.submit_job.assert_called_once()
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_with_all_parameters(self, mock_client_class, mock_load_config):
        """Test submitting job with all parameters"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                # Use (default async mode)
                result = submit_command(
                    command=["python", temp_script, "arg1", "arg2"],
                    req="4",
                    depends_on=["job_1", "job_2"],
                    name="my-job",
                    priority=5,
                    env=["KEY1=value1", "KEY2=value2"],
                    working_dir="/tmp/work"
                )
                assert result == 0
                # Verify all parameters passed through
                call_kwargs = mock_client.submit_job.call_args[1]
                assert call_kwargs['command'] == ["python", temp_script, "arg1", "arg2"]
                assert call_kwargs['requirements'] == "4"
                assert call_kwargs['name'] == "my-job"
                assert call_kwargs['working_dir'] == "/tmp/work"
                assert call_kwargs['env_vars']['KEY1'] == "value1"
                assert call_kwargs['env_vars']['KEY2'] == "value2"
                assert call_kwargs['dependencies'] == ["job_1", "job_2"]
                assert call_kwargs['priority'] == 5
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_validation_exception(self, mock_client_class, mock_load_config):
        """Test handling ValidationException"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.side_effect = ValidationException("Invalid requirements")
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                result = submit_command(command=["python", temp_script], req="invalid")
                assert result == 2
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                result = submit_command(command=["python", temp_script])
                assert result == 3
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_async_mode(self, mock_client_class, mock_load_config):
        """Test async submission mode (default)"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                result = submit_command(
                    command=["python", temp_script]  )
                assert result == 0
                pass  # stream_job_logs removed  # Should not stream in async mode
        finally:
            os.unlink(temp_script)

    @pytest.mark.skip(reason="Block mode not implemented in current version")
    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_wait_for_completion(self, mock_client_class, mock_load_config):
        """Test waiting for job completion with block mode"""
        mock_completed_job = Mock(spec_set=Job)
        mock_completed_job.job_id = "job_123"
        mock_completed_job.status.value = "completed"
        mock_completed_job.exit_code = 0
        mock_completed_job.error_message = None

        mock_pending_job = Mock(spec_set=Job)
        mock_pending_job.job_id = "job_123"
        mock_pending_job.status.value = "running"

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_pending_job
        pass  # stream_job_logs removed
        mock_client.get_job.return_value = mock_completed_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                result = submit_command(command=["python", temp_script])
                assert result == 0  # Completed successfully
                pass  # stream_job_logs removed
        finally:
            os.unlink(temp_script)

    @pytest.mark.skip(reason="Block mode not implemented in current version")
    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_wait_for_failure(self, mock_client_class, mock_load_config):
        """Test waiting for job failure with block mode"""
        mock_failed_job = Mock(spec_set=Job)
        mock_failed_job.job_id = "job_123"
        mock_failed_job.status.value = "failed"
        mock_failed_job.exit_code = 1
        mock_failed_job.error_message = "Error occurred"

        mock_pending_job = Mock(spec_set=Job)
        mock_pending_job.job_id = "job_123"
        mock_pending_job.status.value = "running"

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_pending_job
        pass  # stream_job_logs removed
        mock_client.get_job.return_value = mock_failed_job
        mock_client.get_job_logs.return_value = "stderr content"
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo', autospec=True):
                result = submit_command(command=["python", temp_script])
                assert result == 1  # Failed
                # Should fetch stderr on failure
                mock_client.get_job_logs.assert_called_with(mock_failed_job.job_id, stderr=True)
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_python_command(self, mock_client_class, mock_load_config):
        """Test submitting a python command with arguments"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.submit.click.echo', autospec=True):
            result = submit_command(
                command=["python", "train.py", "--epochs", "10", "--lr", "0.01"]
            )
            assert result == 0
            call_kwargs = mock_client.submit_job.call_args[1]
            assert call_kwargs['command'] == ["python", "train.py", "--epochs", "10", "--lr", "0.01"]

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_bash_command(self, mock_client_class, mock_load_config):
        """Test submitting a bash command with arguments"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_456"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.submit.click.echo', autospec=True):
            result = submit_command(
                command=["bash", "run.sh", "arg1", "arg2"]
            )
            assert result == 0
            call_kwargs = mock_client.submit_job.call_args[1]
            assert call_kwargs['command'] == ["bash", "run.sh", "arg1", "arg2"]

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_executable_command(self, mock_client_class, mock_load_config):
        """Test submitting an executable with options"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_789"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.submit.click.echo', autospec=True):
            result = submit_command(
                command=["./myexec", "--option", "value", "--flag"]
            )
            assert result == 0
            call_kwargs = mock_client.submit_job.call_args[1]
            assert call_kwargs['command'] == ["./myexec", "--option", "value", "--flag"]

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_command_with_conflicting_arguments(self, mock_client_class, mock_load_config):
        """Test that command arguments are preserved even when they conflict with submit options"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_conflict_test"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with patch('scheduler.cli.submit.click.echo', autospec=True):
            # Test complex command with arguments that could conflict with submit options
            # Including: --aaa=1, -d, --async2, -f, --ff, file.txt, --req=1, -D, --name, 2, -g, --env, --name, 3
            result = submit_command(
                command=["cmd", "--aaa=1", "-d", "--async2", "-f", "--ff", "file.txt", 
                         "--req=1", "-D", "--name", "2", "-g", "--env", "--name", "3"]
            )
            assert result == 0
            call_kwargs = mock_client.submit_job.call_args[1]
            # Verify full command is preserved in exact order
            expected_cmd = ["cmd", "--aaa=1", "-d", "--async2", "-f", "--ff", "file.txt", 
                           "--req=1", "-D", "--name", "2", "-g", "--env", "--name", "3"]
            assert call_kwargs['command'] == expected_cmd

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_generic_exception(self, mock_client_class, mock_load_config):
        """Test handling of generic exception during submission"""
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.side_effect = RuntimeError("Unexpected error occurred")
        mock_client_class.return_value = mock_client
        
        with patch('scheduler.cli.submit.click.echo', autospec=True):
            result = submit_command(
                command=["python", "script.py"]
            )
            assert result == 1

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_with_resolved_dependencies(self, mock_client_class, mock_load_config):
        """Test submission with dependencies that get resolved by server"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_456"
        mock_job.status.value = "pending"
        # Server resolved "latest-train" to actual job ID
        mock_job.dependencies = ["job-123", "job-124"]
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client
        
        with patch('scheduler.cli.submit.click.echo', autospec=True) as mock_echo:
            result = submit_command(
                command=["python", "script.py"],
                depends_on=["latest-train", "job-124"]
            )
            assert result == 0
            # Verify dependencies are displayed with resolution markers
            echo_calls = [str(call) for call in mock_echo.call_args_list]
            # Should show "job-123 (resolved)" since latest-train was resolved to job-123
            assert any("job-123 (resolved)" in str(call) for call in echo_calls)

    @patch('scheduler.cli.submit.load_config', autospec=True)
    @patch('scheduler.cli.submit.SchedulerClient', autospec=True)
    def test_submit_with_unresolved_dependencies(self, mock_client_class, mock_load_config):
        """Test submission with dependencies that don't need resolution"""
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_789"
        mock_job.status.value = "pending"
        # Dependencies passed through unchanged
        mock_job.dependencies = ["job-100", "job-200"]
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client
        
        with patch('scheduler.cli.submit.click.echo', autospec=True) as mock_echo:
            result = submit_command(
                command=["python", "script.py"],
                depends_on=["job-100", "job-200"]
            )
            assert result == 0
            # Verify dependencies are displayed without resolution markers
            echo_calls = [str(call) for call in mock_echo.call_args_list]
            # Should show plain job IDs since they weren't resolved
            assert any("job-100" in str(call) and "(resolved)" not in str(call) for call in echo_calls)


