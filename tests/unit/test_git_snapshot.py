"""Unit tests for GitSnapshotManager with shadow repository"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, create_autospec
import pytest

from scheduler.core.config import Config
from scheduler.worker.git_snapshot import GitSnapshotManager


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = create_autospec(Config, instance=True, spec_set=True)
    # Config doesn't have node attribute by default, so we add it as needed by tests
    # This is OK because Config is a dataclass that may have optional attributes
    return config


@pytest.fixture
def git_manager(mock_config):
    """Create a GitSnapshotManager instance"""
    return GitSnapshotManager(mock_config)


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
    
    def test_shadow_repo_path_generation(self, git_manager, temp_work_dir):
        """Test that shadow repo path is generated correctly"""
        shadow_path = git_manager._get_shadow_repo_path(temp_work_dir)
        assert shadow_path == os.path.join(temp_work_dir, '.scheduler-git')


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
        # Create the file
        with open(py_file, 'w') as f:
            f.write('# test\n')
        assert git_manager._should_include_file(py_file, temp_work_dir) is True
    
    def test_should_include_config_file(self, git_manager, temp_work_dir):
        """Test that config files are included"""
        yaml_file = os.path.join(temp_work_dir, 'config.yaml')
        # Create the file
        with open(yaml_file, 'w') as f:
            f.write('test: value\n')
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
        
        # Check branch exists in the workspace's shadow repo
        shadow_repo_path = git_manager._get_shadow_repo_path(temp_work_dir)
        # .scheduler-git IS the git directory (no .git subfolder)
        git_dir = shadow_repo_path
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'branch', '--list', f'job-{job_id}'],
            cwd=temp_work_dir,
            stdout=subprocess.PIPE,
            text=True
        )
        assert f'job-{job_id}' in result.stdout
    
    def test_snapshot_contains_files(self, git_manager, temp_work_dir):
        """Test that snapshot contains the expected files"""
        snapshot_ref = git_manager.create_snapshot('job789', temp_work_dir)
        
        # Get files in the snapshot from workspace's shadow repo
        shadow_repo_path = git_manager._get_shadow_repo_path(temp_work_dir)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=temp_work_dir,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        
        files = result.stdout.strip().split('\n')
        assert 'train.py' in files
        assert 'config.yaml' in files
    
    def test_returns_none_for_directory_with_no_includable_files(self, git_manager):
        """Test that directory with only excluded files returns None"""
        empty_dir = tempfile.mkdtemp()
        try:
            # Create only excluded files
            os.makedirs(os.path.join(empty_dir, '__pycache__'), exist_ok=True)
            with open(os.path.join(empty_dir, '__pycache__', 'test.pyc'), 'w') as f:
                f.write('bytecode')
            
            snapshot_ref = git_manager.create_snapshot('job_empty', empty_dir)
            # Should return None since no includable files
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
        shadow_repo_path = git_manager._get_shadow_repo_path(temp_work_dir)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=temp_work_dir,
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
            result = git_manager.restore_snapshot('job_restore', snapshot_ref, temp_work_dir, restore_dir)
            
            # Should succeed
            assert result is True
            
            # Check files were restored
            assert os.path.exists(os.path.join(restore_dir, 'train.py'))
            assert os.path.exists(os.path.join(restore_dir, 'config.yaml'))
            
        finally:
            # Cleanup worktree
            git_manager.cleanup_snapshot('job_restore', snapshot_ref, temp_work_dir, restore_dir)
    
    def test_restore_returns_false_for_none_ref(self, git_manager, temp_work_dir):
        """Test that restore returns False for None snapshot_ref"""
        result = git_manager.restore_snapshot('job_none', None, temp_work_dir, '/tmp/target')
        assert result is False
    
    def test_restore_returns_false_for_empty_ref(self, git_manager, temp_work_dir):
        """Test that restore returns False for empty snapshot_ref"""
        result = git_manager.restore_snapshot('job_empty', '', temp_work_dir, '/tmp/target')
        assert result is False


class TestCleanupSnapshot:
    """Test cleanup_snapshot method"""
    
    def test_cleanup_removes_worktree(self, git_manager, temp_work_dir):
        """Test that cleanup removes the worktree"""
        # Create and restore snapshot
        snapshot_ref = git_manager.create_snapshot('job_cleanup', temp_work_dir)
        restore_dir = tempfile.mkdtemp()
        
        git_manager.restore_snapshot('job_cleanup', snapshot_ref, temp_work_dir, restore_dir)
        
        # Verify worktree exists
        assert os.path.exists(restore_dir)
        
        # Cleanup
        git_manager.cleanup_snapshot('job_cleanup', snapshot_ref, temp_work_dir, restore_dir)
        
        # Worktree should be removed
        shadow_repo_path = git_manager._get_shadow_repo_path(temp_work_dir)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'worktree', 'list'],
            cwd=temp_work_dir,
            stdout=subprocess.PIPE,
            text=True
        )
        assert restore_dir not in result.stdout
    
    def test_cleanup_handles_none_worktree(self, git_manager, temp_work_dir):
        """Test that cleanup handles None worktree gracefully"""
        # Should not raise exception
        git_manager.cleanup_snapshot('job_test', 'abc123', temp_work_dir, None)
    
    def test_cleanup_handles_nonexistent_worktree(self, git_manager, temp_work_dir):
        """Test that cleanup handles nonexistent worktree gracefully"""
        # Should not raise exception
        git_manager.cleanup_snapshot('job_test', 'abc123', temp_work_dir, '/nonexistent/path')


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
        success = git_manager.restore_snapshot(job_id, snapshot_ref, temp_work_dir, restore_dir)
        assert success is True
        
        # 3. Verify restored files
        assert os.path.exists(os.path.join(restore_dir, 'train.py'))
        with open(os.path.join(restore_dir, 'train.py'), 'r') as f:
            content = f.read()
        assert 'training' in content
        
        # 4. Cleanup
        git_manager.cleanup_snapshot(job_id, snapshot_ref, temp_work_dir, restore_dir)
        
        # Verify cleanup
        shadow_repo_path = git_manager._get_shadow_repo_path(temp_work_dir)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'worktree', 'list'],
            cwd=temp_work_dir,
            stdout=subprocess.PIPE,
            text=True
        )
        assert restore_dir not in result.stdout
