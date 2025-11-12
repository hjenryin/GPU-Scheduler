"""Tests for job executor functionality"""
import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock, mock_open, create_autospec

from scheduler.worker.job_executor import JobExecutor
from scheduler.worker.git_snapshot import GitSnapshotManager
from scheduler.core.models import Job, JobRequirement, JobStatus
from scheduler.core.exceptions import JobNotFoundException
import subprocess


class TestJobExecutor:
    """Tests for JobExecutor class"""

    def test_init(self, test_config):
        """Test job executor initialization"""
        executor = JobExecutor(test_config)

        assert executor.config == test_config
        assert executor.file_handler is not None
        assert executor.processes == {}

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_success(self, mock_file, mock_popen, test_config, sample_job):
        """Test successful job execution"""
        # Setup mock process
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)

        # Execute job
        gpu_ids = [0, 1]
        pid = executor.execute_job(sample_job, gpu_ids)

        # Verify
        assert pid == 12345
        assert 12345 in executor.processes
        assert executor.processes[12345] == mock_process

        # Check that Popen was called with correct arguments
        mock_popen.assert_called_once()
        call_args = mock_popen.call_args

        # Check command - Command is executed as-is without modification
        expected_cmd = [sample_job.script] + sample_job.script_args
        assert call_args[0][0] == expected_cmd

        # Check environment variables
        env = call_args[1]['env']
        assert env['CUDA_VISIBLE_DEVICES'] == '0,1'
        assert env['PYTHONPATH'] == '/home/user/lib'  # From sample_job

        # Check working directory
        assert call_args[1]['cwd'] == sample_job.working_dir

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_no_script_args(self, mock_file, mock_popen, test_config):
        """Test job execution without script arguments"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)

        job = Job(
            job_id="test-job",
            name="test",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            working_dir="/tmp/test"
        )

        pid = executor.execute_job(job, [0])

        # Check command is script only, no args
        call_args = mock_popen.call_args
        expected_cmd = [job.script]
        assert call_args[0][0] == expected_cmd

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_no_env_vars(self, mock_file, mock_popen, test_config):
        """Test job execution without custom environment variables"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)

        job = Job(
            job_id="test-job",
            name="test",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            working_dir="/tmp/test"
        )

        pid = executor.execute_job(job, [2])

        # Check environment has CUDA_VISIBLE_DEVICES but no custom vars
        call_args = mock_popen.call_args
        env = call_args[1]['env']
        assert env['CUDA_VISIBLE_DEVICES'] == '2'

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_multiple_gpus(self, mock_file, mock_popen, test_config, sample_job):
        """Test job execution with multiple GPUs"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)

        gpu_ids = [0, 1, 2, 3]
        pid = executor.execute_job(sample_job, gpu_ids)

        # Check CUDA_VISIBLE_DEVICES
        call_args = mock_popen.call_args
        env = call_args[1]['env']
        assert env['CUDA_VISIBLE_DEVICES'] == '0,1,2,3'

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_no_working_dir(self, mock_file, mock_popen, test_config):
        """Test that JobExecutor raises error when working_dir is None"""
        import os
        mock_process = mock_popen.return_value
        mock_process.pid = 12345

        executor = JobExecutor(test_config)

        job = Job(
            job_id="test-job",
            name="test",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            working_dir=None  # None working_dir should trigger assertion -> RuntimeError
        )

        # Should raise RuntimeError due to None working_dir assertion
        with pytest.raises(RuntimeError, match="working_dir must not be None"):
            pid = executor.execute_job(job, [0])

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_script_not_found(self, mock_file, mock_popen, test_config, sample_job):
        """Test job execution when script file not found"""
        mock_popen.side_effect = FileNotFoundError("Script not found")

        executor = JobExecutor(test_config)

        with pytest.raises(RuntimeError, match="Script not found"):
            executor.execute_job(sample_job, [0])

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_generic_error(self, mock_file, mock_popen, test_config, sample_job):
        """Test job execution with generic error"""
        mock_popen.side_effect = Exception("Some error")

        executor = JobExecutor(test_config)

        with pytest.raises(RuntimeError, match="Failed to execute job"):
            executor.execute_job(sample_job, [0])

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_get_job_status_running(self, mock_file, mock_popen, test_config, sample_job):
        """Test getting status of running job"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Still running


        executor = JobExecutor(test_config)
        pid = executor.execute_job(sample_job, [0])

        is_running, exit_code = executor.get_job_status(pid)

        assert is_running is True
        assert exit_code is None
        assert pid in executor.processes  # Still tracked

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_get_job_status_completed_success(self, mock_file, mock_popen, test_config, sample_job):
        """Test getting status of completed job (success)"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345
        mock_process.poll.return_value = 0  # Completed successfully


        executor = JobExecutor(test_config)
        pid = executor.execute_job(sample_job, [0])

        is_running, exit_code = executor.get_job_status(pid)

        assert is_running is False
        assert exit_code == 0
        assert pid not in executor.processes  # Cleaned up

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_get_job_status_completed_failure(self, mock_file, mock_popen, test_config, sample_job):
        """Test getting status of completed job (failure)"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345
        mock_process.poll.return_value = 1  # Failed


        executor = JobExecutor(test_config)
        pid = executor.execute_job(sample_job, [0])

        is_running, exit_code = executor.get_job_status(pid)

        assert is_running is False
        assert exit_code == 1
        assert pid not in executor.processes  # Cleaned up

    @patch('os.kill', autospec=True)
    def test_get_job_status_untracked_process_exists(self, mock_kill, test_config):
        """Test getting status of untracked process that exists"""
        executor = JobExecutor(test_config)

        # pid not in executor.processes
        mock_kill.return_value = None  # Process exists

        is_running, exit_code = executor.get_job_status(99999)

        assert is_running is True
        assert exit_code is None
        mock_kill.assert_called_once_with(99999, 0)

    @patch('os.kill', autospec=True)
    def test_get_job_status_untracked_process_not_exists(self, mock_kill, test_config):
        """Test getting status of untracked process that doesn't exist"""
        executor = JobExecutor(test_config)

        # pid not in executor.processes
        mock_kill.side_effect = OSError("No such process")

        is_running, exit_code = executor.get_job_status(99999)

        assert is_running is False
        assert exit_code == -1

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_terminate_job_tracked(self, mock_file, mock_popen, test_config, sample_job):
        """Test terminating tracked job"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)
        pid = executor.execute_job(sample_job, [0])

        # Terminate job
        executor.terminate_job(pid)

        mock_process.terminate.assert_called_once()
        assert pid not in executor.processes

    @patch('os.kill', autospec=True)
    def test_terminate_job_untracked(self, mock_kill, test_config):
        """Test terminating untracked job"""
        import signal
        executor = JobExecutor(test_config)

        executor.terminate_job(99999)

        mock_kill.assert_called_once_with(99999, signal.SIGTERM)

    @patch('os.kill', autospec=True)
    def test_terminate_job_error(self, mock_kill, test_config):
        """Test job termination error handling"""
        mock_kill.side_effect = OSError("Permission denied")

        executor = JobExecutor(test_config)

        # Should not raise, just log warning
        executor.terminate_job(99999)

    @patch('os.path.exists', autospec=True)
    @patch('builtins.open', new_callable=mock_open, read_data="Line 1\nLine 2\nLine 3\n")
    def test_get_job_logs_all_lines(self, mock_file, mock_exists, test_config):
        """Test getting all job logs"""
        mock_exists.return_value = True

        executor = JobExecutor(test_config)
        logs = executor.get_job_logs("job-001", lines=None, stderr=False)

        assert logs == "Line 1\nLine 2\nLine 3\n"

    @patch('os.path.exists', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_get_job_logs_last_n_lines(self, mock_file, mock_exists, test_config):
        """Test getting last N lines of job logs"""
        mock_exists.return_value = True
        mock_file.return_value.readlines.return_value = [
            "Line 1\n",
            "Line 2\n",
            "Line 3\n",
            "Line 4\n",
            "Line 5\n"
        ]

        executor = JobExecutor(test_config)
        logs = executor.get_job_logs("job-001", lines=2, stderr=False)

        assert logs == "Line 4\nLine 5\n"

    @patch('os.path.exists', autospec=True)
    def test_get_job_logs_stderr(self, mock_exists, test_config):
        """Test getting stderr logs"""
        mock_exists.return_value = True

        executor = JobExecutor(test_config)

        with patch('builtins.open', mock_open(read_data="Error message\n")):
            logs = executor.get_job_logs("job-001", stderr=True)

        assert logs == "Error message\n"

    @patch('os.path.exists', autospec=True)
    def test_get_job_logs_not_found(self, mock_exists, test_config):
        """Test getting logs for non-existent job"""
        mock_exists.return_value = False

        executor = JobExecutor(test_config)

        with pytest.raises(JobNotFoundException, match="Log file not found"):
            executor.get_job_logs("job-999")

    @patch('os.path.exists', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_get_job_logs_read_error(self, mock_file, mock_exists, test_config):
        """Test log reading error handling"""
        mock_exists.return_value = True
        mock_file.side_effect = Exception("Read error")

        executor = JobExecutor(test_config)

        with pytest.raises(JobNotFoundException, match="Failed to read logs"):
            executor.get_job_logs("job-001")

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_log_files_created(self, mock_file, mock_popen, test_config, sample_job):
        """Test that stdout and stderr log files are created"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)
        executor.execute_job(sample_job, [0])

        # Verify open was called for both stdout and stderr
        assert mock_file.call_count == 2

        # Check that files were opened with correct paths
        calls = mock_file.call_args_list
        stdout_path = calls[0][0][0]
        stderr_path = calls[1][0][0]

        assert sample_job.job_id in stdout_path
        assert sample_job.job_id in stderr_path
        assert 'stdout' in stdout_path
        assert 'stderr' in stderr_path

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_process_group_created(self, mock_file, mock_popen, test_config, sample_job):
        """Test that process is started in new session (new process group)"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345


        executor = JobExecutor(test_config)
        executor.execute_job(sample_job, [0])

        # Verify start_new_session was set
        call_args = mock_popen.call_args
        assert call_args[1]['start_new_session'] is True

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_with_snapshot(self, mock_file, mock_popen, test_config):
        """Test job execution with git snapshot"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345

        executor = JobExecutor(test_config)
        
        # Mock git snapshot manager - use Mock with side_effect for correct signature
        executor.git_snapshot.restore_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, target_dir: True)
        
        # Create job with snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace"
        )
        
        pid = executor.execute_job(job, [0])
        
        # Verify snapshot was restored
        executor.git_snapshot.restore_snapshot.assert_called_once()
        call_args = executor.git_snapshot.restore_snapshot.call_args
        assert call_args[0][0] == "test-job"
        assert call_args[0][1] == "abc123"
        assert call_args[0][2] == "/workspace"
        
        # Verify job is tracked in worktrees
        assert "test-job" in executor.job_worktrees
        
        # Verify execution happened
        assert pid == 12345

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_with_snapshot_in_subdirectory(self, mock_file, mock_popen, test_config):
        """Test job execution with script in subdirectory"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345

        executor = JobExecutor(test_config)
        
        # Mock git snapshot manager - use Mock with side_effect for correct signature
        executor.git_snapshot.restore_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, target_dir: True)
        
        # Create job with script in subdirectory
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/scripts/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace"
        )
        
        pid = executor.execute_job(job, [0])
        
        # Verify command uses relative path
        call_args = mock_popen.call_args
        cmd = call_args[0][0]
        # Script path should preserve subdirectory structure (it's cmd[0] now)
        assert "scripts/train.py" in cmd[0] or "scripts\\train.py" in cmd[0]
        
        assert pid == 12345

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_snapshot_restore_failure(self, mock_file, mock_popen, test_config):
        """Test job execution falls back when snapshot restore fails"""
        mock_process = mock_popen.return_value
        mock_process.pid = 12345

        executor = JobExecutor(test_config)

        # Mock git snapshot manager to fail restore
        executor.git_snapshot.restore_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, target_dir: False)
        
        # Create job with snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            working_dir="/workspace",
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace"
        )
        
        pid = executor.execute_job(job, [0])
        
        # Verify fallback to original working directory
        call_args = mock_popen.call_args
        assert call_args[1]['cwd'] == "/workspace"
        
        # Verify job is NOT tracked in worktrees
        assert "test-job" not in executor.job_worktrees
        
        assert pid == 12345

    def test_cleanup_job_with_snapshot(self, test_config):
        """Test cleanup creates completion snapshot"""
        executor = JobExecutor(test_config)
        
        # Mock git snapshot manager
        executor.git_snapshot.cleanup_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, worktree_path: "completion_ref")
        
        # Create job with snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace",
            working_dir="/workspace"
        )
        
        # Add to worktrees tracking
        worktree_path = "/tmp/worktree"
        executor.job_worktrees[job.job_id] = worktree_path
        
        # Cleanup
        result = executor.cleanup_job(job)
        
        # Verify cleanup_snapshot was called with correct parameters
        executor.git_snapshot.cleanup_snapshot.assert_called_once_with(
            "test-job",  # job_id
            "abc123",  # snapshot_ref
            "/workspace",  # snapshot_working_dir
            worktree_path
        )
        
        # Verify after_commit_ref is returned
        assert result == "completion_ref"
        
        # Verify cleanup was called
        executor.git_snapshot.cleanup_snapshot.assert_called_once()
        
        # Verify worktree was removed from tracking
        assert job.job_id not in executor.job_worktrees

    def test_cleanup_job_without_snapshot(self, test_config):
        """Test cleanup without snapshot"""
        executor = JobExecutor(test_config)
        
        # Create job without snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        
        # Cleanup should not fail
        executor.cleanup_job(job)
        
        # No errors should occur

    def test_cleanup_job_completion_snapshot_failure(self, test_config):
        """Test cleanup continues even if completion snapshot fails"""
        executor = JobExecutor(test_config)
        
        # Mock git snapshot manager to fail completion snapshot
        def raise_error(job_id, working_dir):
            raise Exception("Snapshot failed")
        executor.git_snapshot.create_snapshot = Mock(side_effect=raise_error)
        executor.git_snapshot.cleanup_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, worktree_path: None)
        
        # Create job with snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace"
        )
        
        # Add to worktrees tracking
        worktree_path = "/tmp/worktree"
        executor.job_worktrees[job.job_id] = worktree_path
        
        # Cleanup should not fail even if completion snapshot fails
        executor.cleanup_job(job)
        
        # Verify cleanup was still called
        executor.git_snapshot.cleanup_snapshot.assert_called_once()
        
        # Verify worktree was removed from tracking
        assert job.job_id not in executor.job_worktrees

    @patch('scheduler.worker.job_executor.subprocess.Popen', autospec=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_execute_job_snapshot_script_not_found_cleanup(self, mock_file, mock_popen, test_config):
        """Test that worktree is cleaned up when script not found"""
        # Mock Popen to raise FileNotFoundError
        mock_popen.side_effect = FileNotFoundError("Script not found")

        executor = JobExecutor(test_config)
        
        # Mock git snapshot manager - use Mock with side_effect for correct signature
        executor.git_snapshot.restore_snapshot = Mock(side_effect=lambda job_id, snapshot_ref, working_dir, target_dir: True)
        executor.git_snapshot.cleanup_snapshot = create_autospec(GitSnapshotManager.cleanup_snapshot)
        
        # Create job with snapshot
        job = Job(
            job_id="test-job",
            name="test",
            script="/workspace/train.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING,
            snapshot_ref="abc123",
            snapshot_working_dir="/workspace"
        )
        
        # Manually add to worktrees (since restore is mocked)
        worktree_path = "/tmp/worktree"
        executor.job_worktrees[job.job_id] = worktree_path
        
        # Execute should raise RuntimeError
        with pytest.raises(RuntimeError, match="Script not found"):
            executor.execute_job(job, [0])
        
        # Verify cleanup was called
        executor.git_snapshot.cleanup_snapshot.assert_called_once()
        
        # Verify worktree was removed from tracking
        assert job.job_id not in executor.job_worktrees
