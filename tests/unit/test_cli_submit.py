"""Unit tests for scheduler.cli.submit module"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
from scheduler.cli.submit import submit_command
from scheduler.api import SchedulerClient
from scheduler.core.exceptions import ValidationException, ConnectionException


class TestSubmitCommand:
    """Tests for submit_command function"""

    def test_submit_script_not_found(self):
        """Test submitting a non-existent script"""
        result = submit_command(
            script="/nonexistent/script.py",
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
                script=temp_script,
                env=["INVALID_FORMAT_NO_EQUALS"]
            )
            assert result == 2
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_success(self, mock_client_class, mock_load_config):
        """Test successful job submission"""
        mock_job = Mock()
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"

        mock_client = Mock()
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'):
                # Use async_submit to avoid waiting loop
                result = submit_command(
                    script=temp_script,
                    req="2",
                    name="test_job",
                    async_submit=True
                )
                assert result == 0
                mock_client.submit_job.assert_called_once()
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_with_all_parameters(self, mock_client_class, mock_load_config):
        """Test submitting job with all parameters"""
        mock_job = Mock()
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"

        mock_client = Mock()
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'):
                # Use async_submit to avoid waiting loop
                result = submit_command(
                    script=temp_script,
                    script_args=["arg1", "arg2"],
                    req="4",
                    depends_on=["job_1", "job_2"],
                    name="my-job",
                    priority=5,
                    env=["KEY1=value1", "KEY2=value2"],
                    working_dir="/tmp/work",
                    async_submit=True
                )
                assert result == 0
                # Verify all parameters passed through
                call_kwargs = mock_client.submit_job.call_args[1]
                assert call_kwargs['script'] == os.path.abspath(temp_script)
                assert call_kwargs['requirements'] == "4"
                assert call_kwargs['name'] == "my-job"
                assert call_kwargs['script_args'] == ["arg1", "arg2"]
                assert call_kwargs['working_dir'] == "/tmp/work"
                assert call_kwargs['env_vars']['KEY1'] == "value1"
                assert call_kwargs['env_vars']['KEY2'] == "value2"
                assert call_kwargs['dependencies'] == ["job_1", "job_2"]
                assert call_kwargs['priority'] == 5
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_validation_exception(self, mock_client_class, mock_load_config):
        """Test handling ValidationException"""
        mock_client = Mock()
        mock_client.submit_job.side_effect = ValidationException("Invalid requirements")
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'):
                result = submit_command(script=temp_script, req="invalid")
                assert result == 2
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_connection_exception(self, mock_client_class, mock_load_config):
        """Test handling ConnectionException"""
        mock_client = Mock()
        mock_client.submit_job.side_effect = ConnectionException("Cannot connect")
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'):
                result = submit_command(script=temp_script)
                assert result == 3
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_async_mode(self, mock_client_class, mock_load_config):
        """Test async submission mode"""
        mock_job = Mock()
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"

        mock_client = Mock()
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'):
                result = submit_command(
                    script=temp_script,
                    async_submit=True
                )
                assert result == 0
                mock_client.get_job.assert_not_called()  # Should not poll in async mode
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_wait_for_completion(self, mock_client_class, mock_load_config):
        """Test waiting for job completion"""
        mock_completed_job = Mock()
        mock_completed_job.job_id = "job_123"
        mock_completed_job.status.value = "completed"
        mock_completed_job.exit_code = 0
        mock_completed_job.error_message = None

        mock_pending_job = Mock()
        mock_pending_job.status.value = "running"

        mock_client = Mock()
        mock_client.submit_job.return_value = mock_pending_job
        mock_client.get_job.side_effect = [mock_pending_job, mock_completed_job]
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'), \
                 patch('scheduler.cli.submit.time.sleep'):
                result = submit_command(script=temp_script)
                assert result == 0  # Completed successfully
        finally:
            os.unlink(temp_script)

    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_wait_for_failure(self, mock_client_class, mock_load_config):
        """Test waiting for job failure"""
        mock_failed_job = Mock()
        mock_failed_job.job_id = "job_123"
        mock_failed_job.status.value = "failed"
        mock_failed_job.exit_code = 1
        mock_failed_job.error_message = "Error occurred"

        mock_pending_job = Mock()
        mock_pending_job.status.value = "running"

        mock_client = Mock()
        mock_client.submit_job.return_value = mock_pending_job
        mock_client.get_job.side_effect = [mock_pending_job, mock_failed_job]
        mock_client_class.return_value = mock_client

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            temp_script = f.name

        try:
            with patch('scheduler.cli.submit.click.echo'), \
                 patch('scheduler.cli.submit.time.sleep'):
                result = submit_command(script=temp_script)
                assert result == 1  # Failed
        finally:
            os.unlink(temp_script)

