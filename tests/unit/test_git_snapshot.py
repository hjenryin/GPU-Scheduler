"""Unit tests for GitSnapshotManager with shadow repository"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from scheduler.core.config import Config
from scheduler.worker.git_snapshot import GitSnapshotManager


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = Mock(spec=Config)
    config.node = Mock()
    config.node.temp_dir = tempfile.gettempdir()
    return config


@pytest.fixture
def git_manager(mock_config):
    """Create a GitSnapshotManager instance with temp shadow repo"""
    # Create temp dir for shadow repo
    temp_shadow = tempfile.mkdtemp()
    
    # Patch the shadow_repo_path before initialization
    with patch.object(GitSnapshotManager, '__init__', lambda self, config: None):
        manager = GitSnapshotManager(mock_config)
    
    manager.config = mock_config
    manager.shadow_repo_path = temp_shadow
    manager._ensure_shadow_repo()
    
    yield manager
    
    # Cleanup
    if os.path.exists(manager.shadow_repo_path):
        shutil.rmtree(manager.shadow_repo_path, ignore_errors=True)


@pytest.fixture
def temp_work_dir():
    """Create a temporary working directory with some files"""
    temp_dir = tempfile.mkdtemp()
    
    # Create various files
    with open(os.path.join(temp_dir, 'train.py'), 'w') as f:
        f.write('print("training")\n')
    
    with open(os.path.join(temp_dir, 'config.yaml'), 'w') as f:
        f.write('model: resnet50\n')
    
    # Create subdirectory
    os.makedirs(os.path.join(temp_dir, 'src'), exist_ok=True)
    with open(os.path.join(temp_dir, 'src', 'model.py'), 'w') as f:
        f.write('class Model:\n    pass\n')
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestGitSnapshotManager:
    """Test GitSnapshotManager initialization"""
    
    def test_initialization(self, mock_config):
        """Test that GitSnapshotManager initializes correctly"""
        manager = GitSnapshotManager(mock_config)
        assert manager.config == mock_config
        assert manager.shadow_repo_path is not None
    
    def test_shadow_repo_is_initialized(self, git_manager):
        """Test that shadow repo is initialized as git repo"""
        git_dir = os.path.join(git_manager.shadow_repo_path, '.git')
        assert os.path.exists(git_dir)
        
        # Check it's a valid git repo
        result = subprocess.run(
            ['git', 'status'],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        assert result.returncode == 0


class TestIsGitRepository:
    """Test is_git_repository method"""
    
    def test_always_returns_true(self, git_manager, temp_work_dir):
        """Test that we always create snapshots (shadow repo approach)"""
        # With shadow repo, we always create snapshots
        assert git_manager.is_git_repository(temp_work_dir) is True
    
    def test_returns_true_for_nonexistent_dir(self, git_manager):
        """Test that even non-existent dirs return True (shadow repo approach)"""
        assert git_manager.is_git_repository('/nonexistent/path') is True


class TestFileSelection:
    """Test file selection logic"""
    
    def test_should_include_python_file(self, git_manager, temp_work_dir):
        """Test that Python files are included"""
        py_file = os.path.join(temp_work_dir, 'test.py')
        assert git_manager._should_include_file(py_file, temp_work_dir) is True
    
    def test_should_include_config_file(self, git_manager, temp_work_dir):
        """Test that config files are included"""
        yaml_file = os.path.join(temp_work_dir, 'config.yaml')
        assert git_manager._should_include_file(yaml_file, temp_work_dir) is True
    
    def test_should_exclude_pycache(self, git_manager, temp_work_dir):
        """Test that __pycache__ is excluded"""
        pycache = os.path.join(temp_work_dir, '__pycache__', 'test.pyc')
        os.makedirs(os.path.dirname(pycache), exist_ok=True)
        open(pycache, 'w').close()
        assert git_manager._should_include_file(pycache, temp_work_dir) is False
    
    def test_should_exclude_large_files(self, git_manager, temp_work_dir):
        """Test that large files are excluded"""
        large_file = os.path.join(temp_work_dir, 'large.bin')
        # Create a file larger than threshold
        with open(large_file, 'wb') as f:
            f.write(b'x' * (25 * 1024 * 1024))  # 25 MB
        assert git_manager._should_include_file(large_file, temp_work_dir) is False
    
    def test_collect_files(self, git_manager, temp_work_dir):
        """Test collecting files from directory"""
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert len(files) > 0
        assert 'train.py' in files
        assert 'config.yaml' in files
        assert 'src/model.py' in files


class TestCreateSnapshot:
    """Test create_snapshot method"""
    
    def test_creates_snapshot_successfully(self, git_manager, temp_work_dir):
        """Test successful snapshot creation"""
        snapshot_ref = git_manager.create_snapshot('job123', temp_work_dir)
        
        assert snapshot_ref is not None
        assert len(snapshot_ref) == 40  # SHA-1 hash length
    
    def test_creates_branch_for_job(self, git_manager, temp_work_dir):
        """Test that a branch is created for the job"""
        job_id = 'job456'
        snapshot_ref = git_manager.create_snapshot(job_id, temp_work_dir)
        
        # Check branch exists
        result = subprocess.run(
            ['git', 'branch', '--list', f'job-{job_id}'],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            text=True
        )
        assert f'job-{job_id}' in result.stdout
    
    def test_snapshot_contains_files(self, git_manager, temp_work_dir):
        """Test that snapshot contains the expected files"""
        snapshot_ref = git_manager.create_snapshot('job789', temp_work_dir)
        
        # Get files in the snapshot
        result = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        
        files = result.stdout.strip().split('\n')
        assert 'train.py' in files
        assert 'config.yaml' in files
    
    def test_returns_none_for_empty_directory(self, git_manager):
        """Test that empty directory returns None"""
        empty_dir = tempfile.mkdtemp()
        try:
            snapshot_ref = git_manager.create_snapshot('job_empty', empty_dir)
            assert snapshot_ref is None
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)
    
    def test_handles_subdirectories(self, git_manager, temp_work_dir):
        """Test that subdirectories are handled correctly"""
        # Add more nested structure
        nested_dir = os.path.join(temp_work_dir, 'deep', 'nested', 'dir')
        os.makedirs(nested_dir, exist_ok=True)
        with open(os.path.join(nested_dir, 'deep.py'), 'w') as f:
            f.write('# deep file\n')
        
        snapshot_ref = git_manager.create_snapshot('job_nested', temp_work_dir)
        assert snapshot_ref is not None
        
        # Verify nested file is in snapshot
        result = subprocess.run(
            ['git', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        assert 'deep/nested/dir/deep.py' in result.stdout


class TestRestoreSnapshot:
    """Test restore_snapshot method"""
    
    def test_restore_creates_worktree(self, git_manager, temp_work_dir):
        """Test that restore creates a git worktree"""
        # Create snapshot
        snapshot_ref = git_manager.create_snapshot('job_restore', temp_work_dir)
        assert snapshot_ref is not None
        
        # Restore to a new location
        restore_dir = tempfile.mkdtemp()
        try:
            result = git_manager.restore_snapshot('job_restore', snapshot_ref, restore_dir)
            
            # Should succeed
            assert result is True
            
            # Check files were restored
            assert os.path.exists(os.path.join(restore_dir, 'train.py'))
            assert os.path.exists(os.path.join(restore_dir, 'config.yaml'))
            
        finally:
            # Cleanup worktree
            git_manager.cleanup_snapshot('job_restore', snapshot_ref, restore_dir)
    
    def test_restore_returns_false_for_none_ref(self, git_manager):
        """Test that restore returns False for None snapshot_ref"""
        result = git_manager.restore_snapshot('job_none', None, '/tmp/target')
        assert result is False
    
    def test_restore_returns_false_for_empty_ref(self, git_manager):
        """Test that restore returns False for empty snapshot_ref"""
        result = git_manager.restore_snapshot('job_empty', '', '/tmp/target')
        assert result is False


class TestCleanupSnapshot:
    """Test cleanup_snapshot method"""
    
    def test_cleanup_removes_worktree(self, git_manager, temp_work_dir):
        """Test that cleanup removes the worktree"""
        # Create and restore snapshot
        snapshot_ref = git_manager.create_snapshot('job_cleanup', temp_work_dir)
        restore_dir = tempfile.mkdtemp()
        
        git_manager.restore_snapshot('job_cleanup', snapshot_ref, restore_dir)
        
        # Verify worktree exists
        assert os.path.exists(restore_dir)
        
        # Cleanup
        git_manager.cleanup_snapshot('job_cleanup', snapshot_ref, restore_dir)
        
        # Worktree should be removed
        result = subprocess.run(
            ['git', 'worktree', 'list'],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            text=True
        )
        assert restore_dir not in result.stdout
    
    def test_cleanup_handles_none_worktree(self, git_manager):
        """Test that cleanup handles None worktree gracefully"""
        # Should not raise exception
        git_manager.cleanup_snapshot('job_test', 'abc123', None)
    
    def test_cleanup_handles_nonexistent_worktree(self, git_manager):
        """Test that cleanup handles nonexistent worktree gracefully"""
        # Should not raise exception
        git_manager.cleanup_snapshot('job_test', 'abc123', '/nonexistent/path')


class TestIntegration:
    """Integration tests for complete workflow"""
    
    def test_complete_workflow(self, git_manager, temp_work_dir):
        """Test complete create -> restore -> cleanup workflow"""
        job_id = 'job_workflow'
        
        # 1. Create snapshot
        snapshot_ref = git_manager.create_snapshot(job_id, temp_work_dir)
        assert snapshot_ref is not None
        
        # 2. Restore snapshot
        restore_dir = tempfile.mkdtemp()
        success = git_manager.restore_snapshot(job_id, snapshot_ref, restore_dir)
        assert success is True
        
        # 3. Verify restored files
        assert os.path.exists(os.path.join(restore_dir, 'train.py'))
        with open(os.path.join(restore_dir, 'train.py'), 'r') as f:
            content = f.read()
        assert 'training' in content
        
        # 4. Cleanup
        git_manager.cleanup_snapshot(job_id, snapshot_ref, restore_dir)
        
        # Verify cleanup
        result = subprocess.run(
            ['git', 'worktree', 'list'],
            cwd=git_manager.shadow_repo_path,
            stdout=subprocess.PIPE,
            text=True
        )
        assert restore_dir not in result.stdout
