"""Integration tests for git workspace prompting"""
import os
import tempfile
import shutil
import subprocess
import pytest
from unittest.mock import patch, Mock
from scheduler.cli.submit import submit_command
from scheduler.core import Job


class TestGitWorkspacePrompting:
    """Test workspace prompting when not in a git repository"""
    
    @patch('scheduler.cli.submit.SchedulerClient')
    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.click.echo')
    @patch('scheduler.cli.submit.click.confirm')
    def test_prompt_shown_for_non_git_directory(self, mock_confirm, mock_echo, mock_load_config, mock_client_class):
        """Test that prompt is shown when submitting from non-git directory"""
        # Create temporary non-git directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a test script
            script_path = os.path.join(temp_dir, 'test.py')
            with open(script_path, 'w') as f:
                f.write('print("test")\n')
            
            # Mock job response
            mock_job = Mock(spec=Job)
            mock_job.job_id = "job_123"
            mock_job.status.value = "pending"
            
            # Mock client
            mock_client = Mock()
            mock_client.submit_job.return_value = mock_job
            mock_client_class.return_value = mock_client
            
            # User confirms the workspace
            mock_confirm.return_value = True
            
            # Change to non-git directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Submit job
                result = submit_command(
                    command=["python", script_path],
                    req="1",
                    async_submit=True
                )
                
                # Should succeed
                assert result == 0
                
                # Should have shown the warning and prompt
                warning_shown = False
                for call in mock_echo.call_args_list:
                    if 'not in a git repository' in str(call):
                        warning_shown = True
                        break
                assert warning_shown, "Warning about non-git directory should be shown"
                
                # Confirm should have been called
                mock_confirm.assert_called_once()
                
            finally:
                os.chdir(original_cwd)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    @patch('scheduler.cli.submit.SchedulerClient')
    @patch('scheduler.cli.submit.load_config')
    @patch('scheduler.cli.submit.click.echo')
    @patch('scheduler.cli.submit.click.confirm')
    def test_no_prompt_shown_for_git_directory(self, mock_confirm, mock_echo, mock_load_config, mock_client_class):
        """Test that no prompt is shown when submitting from git directory"""
        # Create temporary git directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['git', 'config', 'user.email', 'test@test.com'],
                         cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['git', 'config', 'user.name', 'Test User'],
                         cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Create a test script
            script_path = os.path.join(temp_dir, 'test.py')
            with open(script_path, 'w') as f:
                f.write('print("test")\n')
            
            # Mock job response
            mock_job = Mock(spec=Job)
            mock_job.job_id = "job_123"
            mock_job.status.value = "pending"
            
            # Mock client
            mock_client = Mock()
            mock_client.submit_job.return_value = mock_job
            mock_client_class.return_value = mock_client
            
            # Change to git directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Submit job
                result = submit_command(
                    command=["python", script_path],
                    req="1",
                    async_submit=True
                )
                
                # Should succeed
                assert result == 0
                
                # Should NOT have shown the warning about non-git directory
                warning_shown = False
                for call in mock_echo.call_args_list:
                    if 'not in a git repository' in str(call):
                        warning_shown = True
                        break
                assert not warning_shown, "Warning should not be shown for git directory"
                
                # Confirm should NOT have been called
                mock_confirm.assert_not_called()
                
            finally:
                os.chdir(original_cwd)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
