"""Integration tests for git snapshot functionality"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from scheduler.core.config import Config
from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.head.job_manager import JobManager
from scheduler.head.persistence import PersistenceManager
from scheduler.worker.git_snapshot import GitSnapshotManager


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing"""
    temp_dir = tempfile.mkdtemp()
    
    # Initialize git repo
    subprocess.run(['git', 'init'], cwd=temp_dir, check=True, 
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['git', 'config', 'user.email', 'test@test.com'], 
                   cwd=temp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['git', 'config', 'user.name', 'Test User'], 
                   cwd=temp_dir, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Create initial commit with test script
    test_file = os.path.join(temp_dir, 'train.py')
    with open(test_file, 'w') as f:
        f.write('print("version 1")\n')
    subprocess.run(['git', 'add', '.'], cwd=temp_dir, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(['git', 'commit', '-m', 'Initial commit'], cwd=temp_dir, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_non_git_dir():
    """Create a temporary non-git directory for testing"""
    temp_dir = tempfile.mkdtemp()
    
    # Create a test file
    test_file = os.path.join(temp_dir, 'train.py')
    with open(test_file, 'w') as f:
        f.write('print("hello")\n')
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = Mock(spec=Config)
    config.node = Mock()
    config.node.temp_dir = tempfile.gettempdir()
    config.worker = Mock()
    config.worker.work_dir = tempfile.mkdtemp()
    config.worker.log_dir = tempfile.mkdtemp()
    return config


@pytest.fixture
def mock_persistence():
    """Create a mock persistence manager"""
    persistence = Mock(spec=PersistenceManager)
    persistence.load_all_jobs.return_value = []
    persistence.save_job.return_value = None
    return persistence


@pytest.fixture
def job_manager(mock_config, mock_persistence):
    """Create a JobManager instance with mocked dependencies"""
    return JobManager(mock_persistence, mock_config)


class TestGitSnapshotIntegration:
    """Integration tests for git snapshot feature"""
    
    def test_submit_job_in_git_repo_creates_snapshot(self, job_manager, temp_git_repo):
        """Test that submitting a job in a git repo creates a snapshot"""
        script_path = os.path.join(temp_git_repo, 'train.py')
        
        # Submit job
        job = job_manager.submit_job(
            script=script_path,
            requirements="1",
            working_dir=temp_git_repo
        )
        
        # Verify job was created
        assert job is not None
        assert job.job_id is not None
        assert job.status == JobStatus.PENDING
        
        # Verify snapshot was created
        assert job.snapshot_ref is not None
        assert job.snapshot_working_dir == temp_git_repo
        assert len(job.snapshot_ref) >= 40  # At least a SHA-1 hash
    
    def test_submit_job_in_non_git_dir_creates_snapshot(self, job_manager, temp_non_git_dir):
        """Test that submitting a job in a non-git directory now creates snapshot in shadow repo"""
        script_path = os.path.join(temp_non_git_dir, 'train.py')
        
        # Submit job
        job = job_manager.submit_job(
            script=script_path,
            requirements="1",
            working_dir=temp_non_git_dir
        )
        
        # Verify job was created
        assert job is not None
        assert job.job_id is not None
        assert job.status == JobStatus.PENDING
        
        # With shadow repo approach, we now create snapshots for all directories
        assert job.snapshot_ref is not None
        assert job.snapshot_working_dir == temp_non_git_dir
    
    def test_submit_job_with_uncommitted_changes_creates_snapshot(self, job_manager, temp_git_repo):
        """Test that submitting a job with uncommitted changes creates snapshot (no stash in shadow repo)"""
        script_path = os.path.join(temp_git_repo, 'train.py')
        
        # Modify the file (create uncommitted changes)
        with open(script_path, 'w') as f:
            f.write('print("version 2 - modified")\n')
        
        # Submit job
        job = job_manager.submit_job(
            script=script_path,
            requirements="1",
            working_dir=temp_git_repo
        )
        
        # Verify job was created
        assert job is not None
        assert job.snapshot_ref is not None
        
        # With shadow repo, we just get a single commit SHA (no stash)
        assert len(job.snapshot_ref) == 40  # SHA-1 hash length
        assert ':' not in job.snapshot_ref  # No stash in shadow repo approach
        
        # Verify working directory still has modifications (we don't touch it)
        with open(script_path, 'r') as f:
            content = f.read()
        assert 'version 2 - modified' in content
    
    def test_job_serialization_includes_snapshot_fields(self, job_manager, temp_git_repo):
        """Test that job serialization includes snapshot fields"""
        script_path = os.path.join(temp_git_repo, 'train.py')
        
        # Submit job
        job = job_manager.submit_job(
            script=script_path,
            requirements="1",
            working_dir=temp_git_repo
        )
        
        # Serialize job
        job_dict = job.to_dict()
        
        # Verify snapshot fields are in dictionary
        assert 'snapshot_ref' in job_dict
        assert 'snapshot_working_dir' in job_dict
        assert job_dict['snapshot_ref'] is not None
        assert job_dict['snapshot_working_dir'] == temp_git_repo
        
        # Deserialize job
        restored_job = Job.from_dict(job_dict)
        
        # Verify snapshot fields are restored
        assert restored_job.snapshot_ref == job.snapshot_ref
        assert restored_job.snapshot_working_dir == job.snapshot_working_dir
    
    def test_snapshot_creation_failure_doesnt_break_job_submission(self, job_manager, temp_git_repo):
        """Test that snapshot creation failure doesn't prevent job submission"""
        script_path = os.path.join(temp_git_repo, 'train.py')
        
        # Mock GitSnapshotManager to simulate failure
        with patch('scheduler.head.job_manager.GitSnapshotManager') as MockGitManager:
            mock_manager = MockGitManager.return_value
            mock_manager.is_git_repository.return_value = True
            mock_manager.create_snapshot.side_effect = Exception("Simulated failure")
            
            # Submit job - should not raise exception
            job = job_manager.submit_job(
                script=script_path,
                requirements="1",
                working_dir=temp_git_repo
            )
            
            # Verify job was created despite snapshot failure
            assert job is not None
            assert job.job_id is not None
            assert job.status == JobStatus.PENDING
            # Snapshot fields should be None due to failure
            assert job.snapshot_ref is None


class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality"""
    
    def test_job_without_snapshot_fields_deserializes_correctly(self, job_manager):
        """Test that jobs without snapshot fields can still be deserialized"""
        # Create a job dict without snapshot fields (simulating old data)
        job_dict = {
            'job_id': 'job_123',
            'name': 'test_job',
            'script': '/path/to/script.py',
            'requirements': '1',
            'script_args': [],
            'working_dir': '/path/to/dir',
            'env_vars': {},
            'dependencies': [],
            'priority': 0,
            'submitted_at': '2025-01-01T12:00:00',
            'started_at': None,
            'completed_at': None,
            'status': 'pending',
            'assigned_node': None,
            'assigned_gpus': None,
            'exit_code': None,
            'error_message': None,
            'versioned_script_path': None
            # Note: no snapshot_ref or snapshot_working_dir
        }
        
        # Deserialize - should not fail
        job = Job.from_dict(job_dict)
        
        # Verify job was created correctly
        assert job.job_id == 'job_123'
        assert job.snapshot_ref is None
        assert job.snapshot_working_dir is None
