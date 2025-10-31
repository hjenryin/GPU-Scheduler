"""Unit tests for scheduler.cli.submit_batch module"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, call
from scheduler.cli.submit_batch import submit_batch_command


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

    def test_submit_batch_file_with_blank_lines(self):
        """Test submitting with a file that has blank lines"""
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
            with patch('scheduler.cli.submit_batch.submit_command', return_value=0) as mock_submit, \
                 patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    async_submit=True
                )
                assert result == 0
                # Should only call submit_command twice (blank lines ignored)
                assert mock_submit.call_count == 2
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.submit_command', return_value=0)
    def test_submit_batch_success(self, mock_submit_command):
        """Test successful batch submission"""
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
                    req="2",
                    async_submit=True
                )
                assert result == 0
                # Should call submit_command for each script
                assert mock_submit_command.call_count == 3
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.submit_command', return_value=0)
    def test_submit_batch_with_all_options(self, mock_submit_command):
        """Test batch submission with all options"""
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
                    working_dir="/tmp/work",
                    async_submit=True
                )
                assert result == 0
                assert mock_submit_command.call_count == 2
                
                # Verify all parameters passed through for first call
                first_call = mock_submit_command.call_args_list[0]
                assert first_call[1]['script'] == test_scripts[0]
                assert first_call[1]['req'] == "4"
                assert first_call[1]['depends_on'] == ["job_1", "job_2"]
                assert first_call[1]['name'] == "batch-job"
                assert first_call[1]['priority'] == 5
                assert first_call[1]['env'] == ["KEY1=value1", "KEY2=value2"]
                assert first_call[1]['working_dir'] == "/tmp/work"
                assert first_call[1]['async_submit'] == True
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.submit_command')
    def test_submit_batch_partial_failure(self, mock_submit_command):
        """Test batch submission when some jobs fail"""
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

        # Mock: first succeeds, second fails, third succeeds
        mock_submit_command.side_effect = [0, 1, 0]

        try:
            with patch('scheduler.cli.submit_batch.click.echo'):
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    async_submit=True
                )
                # Should return 1 because at least one failed
                assert result == 1
                assert mock_submit_command.call_count == 3
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.submit_command', return_value=0)
    def test_submit_batch_async_behavior(self, mock_submit_command):
        """Test that batch submission uses async mode correctly"""
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
                # Test with async_submit=False
                result = submit_batch_command(
                    script_list=script_list_file,
                    req="1",
                    async_submit=False
                )
                assert result == 0
                
                # First job should be async (True), last job should respect async_submit (False)
                calls = mock_submit_command.call_args_list
                assert calls[0][1]['async_submit'] == True  # First job: async
                assert calls[1][1]['async_submit'] == False  # Last job: respects user flag
        finally:
            os.unlink(script_list_file)
            for script in test_scripts:
                os.unlink(script)

    @patch('scheduler.cli.submit_batch.submit_command', return_value=0)
    def test_submit_batch_log_to_driver_behavior(self, mock_submit_command):
        """Test that log_to_driver only applies to last job"""
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
                    log_to_driver=True,
                    async_submit=True
                )
                assert result == 0
                
                # Only last job should have log_to_driver=True
                calls = mock_submit_command.call_args_list
                assert calls[0][1]['log_to_driver'] == False  # First job
                assert calls[1][1]['log_to_driver'] == False  # Second job
                assert calls[2][1]['log_to_driver'] == True   # Last job
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
