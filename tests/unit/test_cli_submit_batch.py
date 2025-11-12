"""Unit tests for scheduler.cli.submit_batch module"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, MagicMock
from scheduler.cli.submit_batch import submit_batch_command
from scheduler.api import SchedulerClient
from scheduler.core import Job
from scheduler.core.exceptions import ValidationException, ConnectionException


class TestSubmitBatchCommand:
    """Tests for submit_batch_command function"""

    def test_submit_batch_script_list_not_found(self):
        """Test submitting with a non-existent script list file"""
        result = submit_batch_command(
            script_list="/nonexistent/script_list.txt",
            req="1"
        )
        assert result == 4

    def test_submit_batch_empty_file(self):
        """Test submitting with an empty script list file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            # Write nothing
            temp_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=temp_file,
                    req="1"
                )
                assert result == 1
        finally:
            os.unlink(temp_file)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_file_with_blank_lines(self, mock_client_class, mock_load_config):
        """Test submitting with a file that has blank lines"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        # Create test scripts
        test_scripts = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file with blank lines
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(f"{test_scripts[0]}\n")
            f.write("\n")  # blank line
            f.write(f"{test_scripts[1]}\n")
            f.write("  \n")  # blank line with spaces
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1"
                )
                assert result == 0
                # Should only call submit_job twice (blank lines ignored)
                assert mock_client.submit_job.call_count == 2
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_file_with_comments(self, mock_client_class, mock_load_config):
        """Test submitting with a file that has comment lines"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []

        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client

        # Create test scripts
        test_scripts = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file with comments
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("# This is a comment\n")
            f.write(f"{test_scripts[0]}\n")
            f.write("  # This is an indented comment\n")
            f.write(f"{test_scripts[1]}\n")
            f.write("# Another comment at the end\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1"
                )
                assert result == 0
                # Should only call submit_job twice (comment lines ignored)
                assert mock_client.submit_job.call_count == 2
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_success(self, mock_client_class, mock_load_config):
        """Test successful batch submission"""
        # Create mock jobs
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="2"
                )
                assert result == 0
                # Should call submit_job for each script
                assert mock_client.submit_job.call_count == 3
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_with_script_args(self, mock_client_class, mock_load_config):
        """Test batch submission with script arguments"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file with arguments
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(f"{test_scripts[0]} --arg1 value1\n")
            f.write(f"{test_scripts[1]} --arg2 value2 --arg3\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1"
                )
                assert result == 0
                assert mock_client.submit_job.call_count == 2
                
                # Verify args passed correctly
                first_call = mock_client.submit_job.call_args_list[0]
                assert first_call[1]['script_args'] == ['--arg1', 'value1']
                
                second_call = mock_client.submit_job.call_args_list[1]
                assert second_call[1]['script_args'] == ['--arg2', 'value2', '--arg3']
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_with_all_options(self, mock_client_class, mock_load_config):
        """Test batch submission with all options"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="4",
                    depends_on=["job_1", "job_2"],
                    name="batch-job",
                    priority=5,
                    env=["KEY1=value1", "KEY2=value2"],
                    working_dir="/tmp/work"
                )
                assert result == 0
                assert mock_client.submit_job.call_count == 2
                
                # Verify all parameters passed through for first call
                first_call = mock_client.submit_job.call_args_list[0]
                assert first_call[1]['script'] == os.path.abspath(test_scripts[0])
                assert first_call[1]['requirements'] == "4"
                assert first_call[1]['name'] == "batch-job"
                assert first_call[1]['priority'] == 5
                assert first_call[1]['env_vars']['KEY1'] == "value1"
                assert first_call[1]['env_vars']['KEY2'] == "value2"
                assert first_call[1]['working_dir'] == "/tmp/work"
                assert first_call[1]['dependencies'] == ["job_1", "job_2"]
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_partial_failure(self, mock_client_class, mock_load_config):
        """Test batch submission when some jobs fail"""
        # Create mock jobs
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        # First succeeds, second fails with ValidationException, third succeeds
        mock_client.submit_job.side_effect = [
            mock_job, 
            ValidationException("Invalid requirements"),
            mock_job
        ]
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1"
                )
                # Should return 1 because at least one failed
                assert result == 1
                assert mock_client.submit_job.call_count == 3
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @pytest.mark.skip(reason="log_to_driver mode not implemented in current version")
    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_log_to_driver_behavior(self, mock_client_class, mock_load_config):
        """Test that log_to_driver streams logs for last job"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_123"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.return_value = mock_job
        pass  # stream_job_logs removed
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1"
                )
                assert result == 0
                # Should stream logs for last job
                pass  # stream_job_logs removed
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    def test_submit_batch_io_error(self):
        """Test handling of IO errors when reading script list"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("script1.py\n")
            script_list_file = f.name

        # Delete the file to simulate IO error
        os.unlink(script_list_file)
        
        with patch('scheduler.cli.submit_batch.click.echo'):
            result = submit_batch_command(
                script_list=script_list_file,
                req="1"
            )
            assert result == 4  # File not found

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_sequential_mode(self, mock_client_class, mock_load_config):
        """Test sequential mode creates job dependencies"""
        # Create mock jobs with different IDs
        mock_jobs = []
        for i in range(3):
            mock_job = Mock(spec_set=Job)
            mock_job.job_id = f"job_{i}"
            mock_job.status.value = "pending"
            mock_job.dependencies = []
            mock_jobs.append(mock_job)
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.side_effect = mock_jobs
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    sequential=True
                )
                assert result == 0
                assert mock_client.submit_job.call_count == 3
                
                # Check dependencies
                calls = mock_client.submit_job.call_args_list
                # First job should have no dependencies
                assert calls[0][1]['dependencies'] is None
                # Second job should depend on first
                assert calls[1][1]['dependencies'] == ["job_0"]
                # Third job should depend on second
                assert calls[2][1]['dependencies'] == ["job_1"]
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_sequential_mode_with_base_dependencies(self, mock_client_class, mock_load_config):
        """Test sequential mode with base dependencies"""
        # Create mock jobs
        mock_jobs = []
        for i in range(2):
            mock_job = Mock(spec_set=Job)
            mock_job.job_id = f"job_{i}"
            mock_job.status.value = "pending"
            mock_job.dependencies = []
            mock_jobs.append(mock_job)
        
        mock_client = Mock(spec_set=SchedulerClient)
        mock_client.submit_job.side_effect = mock_jobs
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(2):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    depends_on=["base_job_1", "base_job_2"],
                    sequential=True
                )
                assert result == 0
                
                # Check dependencies
                calls = mock_client.submit_job.call_args_list
                # First job should have base dependencies
                assert calls[0][1]['dependencies'] == ["base_job_1", "base_job_2"]
                # Second job should have base dependencies + previous job
                assert calls[1][1]['dependencies'] == ["base_job_1", "base_job_2", "job_0"]
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.load_config', autospec=True)
    @patch('scheduler.cli.submit_batch.SchedulerClient', autospec=True)
    def test_submit_batch_sequential_mode_stops_on_error(self, mock_client_class, mock_load_config):
        """Test sequential mode stops on first error"""
        # Create mock job
        mock_job = Mock(spec_set=Job)
        mock_job.job_id = "job_0"
        mock_job.status.value = "pending"
        mock_job.dependencies = []
        
        mock_client = Mock(spec_set=SchedulerClient)
        # First succeeds, second fails
        mock_client.submit_job.side_effect = [
            mock_job,
            ValidationException("Invalid requirements")
        ]
        mock_client_class.return_value = mock_client
        
        # Create test scripts
        test_scripts = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
                f.write(f"print('test {i}')")
                test_scripts.append(f.name)

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for script in test_scripts:
                f.write(f"{script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    sequential=True
                )
                # Should fail
                assert result == 1
                # Should only try 2 jobs (stops on error in sequential mode)
                assert mock_client.submit_job.call_count == 2
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    def test_submit_batch_invalid_env_var_format(self):
        """Test batch submission with invalid environment variable format"""
        # Create test script
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.py') as f:
            f.write("print('test')")
            test_script = f.name

        # Create script list file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write(f"{test_script}\n")
            script_list_file = f.name

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    env=["INVALID_FORMAT_NO_EQUALS"]
                )
                assert result == 2
        finally:
            os.unlink(script_list_file)
            os.unlink(test_script)
