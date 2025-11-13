"""Integration tests for working directory handling"""

import os
import tempfile
import shutil
from unittest.mock import Mock, create_autospec
import pytest

from scheduler.core.config import Config, WorkerConfig
from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.core import find_workspace_root
from scheduler.worker.job_executor import JobExecutor
from scheduler.worker.git_snapshot import GitSnapshotManager


@pytest.fixture
def test_config():
    """Create real config instance with temp directories - Config is a frozen dataclass"""
    # Create temporary directories for this test session
    temp_log_dir = tempfile.mkdtemp()
    temp_temp_dir = tempfile.mkdtemp()
    temp_work_dir = tempfile.mkdtemp()

    # Create config with WorkerConfig containing temp directories
    config = Config(
        worker=WorkerConfig(
            work_dir=temp_work_dir,
            log_dir=temp_log_dir,
            temp_dir=temp_temp_dir
        )
    )
    return config


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace with subdirectories"""
    workspace = tempfile.mkdtemp()
    
    # Create directory structure
    subdir = os.path.join(workspace, 'experiments', 'exp1')
    os.makedirs(subdir, exist_ok=True)
    
    # Create test script that outputs pwd
    test_script = os.path.join(subdir, 'test_pwd.sh')
    with open(test_script, 'w') as f:
        f.write('#!/bin/bash\n')
        f.write('pwd\n')
        f.write('echo "Working directory: $(pwd)"\n')
    os.chmod(test_script, 0o755)
    
    # Create a Python script as well
    py_script = os.path.join(subdir, 'test_pwd.py')
    with open(py_script, 'w') as f:
        f.write('import os\n')
        f.write('print(f"Working directory: {os.getcwd()}")\n')
    
    yield {
        'workspace': workspace,
        'subdir': subdir,
        'bash_script': test_script,
        'py_script': py_script
    }
    
    # Cleanup
    shutil.rmtree(workspace, ignore_errors=True)


class TestWorkingDirectoryWithoutSnapshot:
    """Test working directory when no snapshot is used"""
    
    def test_job_executes_in_working_dir(self, test_config, temp_workspace):
        """Test that job executes in the specified working directory"""
        executor = JobExecutor(test_config)
        
        # Create a job with working_dir set to subdirectory
        job = Job(
            job_id='test_job_1',
            name='test_pwd',
            script=temp_workspace['bash_script'],
            requirements=JobRequirement('1'),
            working_dir=temp_workspace['subdir'],
            status=JobStatus.PENDING
        )
        
        # Execute the job
        pid = executor.execute_job(job, gpu_ids=[0])
        assert pid > 0
        
        # Wait for job to complete (it's a quick script)
        import time
        for _ in range(10):
            is_running, exit_code = executor.get_job_status(pid)
            if not is_running:
                break
            time.sleep(0.1)
        
        # Check job completed successfully
        assert not is_running
        assert exit_code == 0
        
        # Check the log contains the correct working directory
        logs = executor.get_job_logs('test_job_1', stderr=False)
        assert temp_workspace['subdir'] in logs, f"Expected {temp_workspace['subdir']} in logs, got: {logs}"


class TestWorkingDirectoryWithSnapshot:
    """Test working directory when snapshot is used"""
    
    def test_job_executes_in_subdirectory_of_worktree(self, test_config, temp_workspace):
        """Test that job executes in correct subdirectory when snapshot is restored"""
        executor = JobExecutor(test_config)
        git_manager = GitSnapshotManager(test_config)
        
        # Create snapshot from workspace root
        result = git_manager.create_snapshot('test_job_2', temp_workspace['workspace'])
        assert result is not None
        snapshot_ref, workspace_root = result
        
        # Create a job that was submitted from subdirectory
        # The snapshot was created from workspace root, but job was submitted from subdir
        job = Job(
            job_id='test_job_2',
            name='test_pwd_snapshot',
            script=temp_workspace['bash_script'],
            requirements=JobRequirement('1'),
            working_dir=temp_workspace['subdir'],
            snapshot_ref=snapshot_ref,
            snapshot_working_dir=workspace_root,  # This is the workspace root
            status=JobStatus.PENDING
        )
        
        # Execute the job
        pid = executor.execute_job(job, gpu_ids=[0])
        assert pid > 0
        
        # Wait for job to complete
        import time
        for _ in range(10):
            is_running, exit_code = executor.get_job_status(pid)
            if not is_running:
                break
            time.sleep(0.1)
        
        # Check job completed successfully
        assert not is_running
        assert exit_code == 0
        
        # Check the log - should show worktree path with subdirectory
        logs = executor.get_job_logs('test_job_2', stderr=False)
        # The working directory should be in worktree, but in the same relative path
        # Check for the subdirectory structure using os.path.sep for platform compatibility
        expected_subpath = f'experiments{os.path.sep}exp1'
        assert expected_subpath in logs, \
            f"Expected {expected_subpath} subdirectory in logs, got: {logs}"
        
        # Cleanup
        executor.cleanup_job(job)


class TestWorkspaceRootDiscovery:
    """Test workspace root discovery for snapshots"""
    
    def test_finds_workspace_root_from_subdirectory(self, test_config):
        """Test that workspace root is found by searching upward"""
        git_manager = GitSnapshotManager(test_config)
        
        # Create workspace with nested directories
        workspace = tempfile.mkdtemp()
        try:
            # Create .git directory at root
            git_dir = os.path.join(workspace, '.git')
            os.makedirs(git_dir, exist_ok=True)
            
            # Create nested subdirectory
            nested = os.path.join(workspace, 'a', 'b', 'c')
            os.makedirs(nested, exist_ok=True)
            
            # Create a file in nested directory
            with open(os.path.join(nested, 'test.py'), 'w') as f:
                f.write('print("hello")\n')
            
            # Find workspace root from nested directory
            found_root = find_workspace_root(nested)

            # Should find the workspace root, not the nested directory
            assert found_root == workspace, f"Expected {workspace}, got {found_root}"
            
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
    
    def test_creates_scheduler_git_at_workspace_root(self, test_config):
        """Test that .scheduler-git is created at workspace root when .git exists"""
        git_manager = GitSnapshotManager(test_config)
        
        workspace = tempfile.mkdtemp()
        try:
            # Create .git directory at workspace root
            git_dir = os.path.join(workspace, '.git')
            os.makedirs(git_dir, exist_ok=True)
            
            # Create nested subdirectory
            nested = os.path.join(workspace, 'experiments', 'exp1')
            os.makedirs(nested, exist_ok=True)
            
            # Create a file in nested directory
            with open(os.path.join(nested, 'test.py'), 'w') as f:
                f.write('print("hello")\n')
            
            # Create snapshot from nested directory
            result = git_manager.create_snapshot('test_job', nested)
            
            # Should create .scheduler-git at workspace root (where .git is)
            scheduler_git = os.path.join(workspace, '.scheduler-git')
            assert os.path.exists(scheduler_git), \
                f"Expected .scheduler-git at {scheduler_git}"
            
            # Should NOT create .scheduler-git in the nested directory
            nested_scheduler_git = os.path.join(nested, '.scheduler-git')
            assert not os.path.exists(nested_scheduler_git), \
                f"Should not create .scheduler-git at {nested_scheduler_git}"
            
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
    
    def test_creates_scheduler_git_in_current_dir_when_no_git(self, test_config):
        """Test that .scheduler-git is created in current dir when no .git is found"""
        git_manager = GitSnapshotManager(test_config)
        
        workspace = tempfile.mkdtemp()
        try:
            # Create nested subdirectory (no .git anywhere)
            nested = os.path.join(workspace, 'experiments', 'exp1')
            os.makedirs(nested, exist_ok=True)
            
            # Create a file in nested directory
            with open(os.path.join(nested, 'test.py'), 'w') as f:
                f.write('print("hello")\n')
            
            # Create snapshot from nested directory
            result = git_manager.create_snapshot('test_job', nested)
            
            # Since there's no .git, should create .scheduler-git in the nested directory
            scheduler_git = os.path.join(nested, '.scheduler-git')
            assert os.path.exists(scheduler_git), \
                f"Expected .scheduler-git at {scheduler_git}"
            
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
