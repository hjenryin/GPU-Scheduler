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
        """Test that __pycache__ is excluded via pattern matching"""
        pycache_dir = os.path.join(temp_work_dir, '__pycache__')
        os.makedirs(pycache_dir, exist_ok=True)
        pycache_file = os.path.join(pycache_dir, 'test.pyc')
        open(pycache_file, 'w').close()

        # Ensure shadow repo exists
        git_manager._ensure_shadow_repo(temp_work_dir)

        # Collect files - __pycache__ should be excluded
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert '__pycache__/test.pyc' not in files, "__pycache__ files should be excluded"
    
    def test_should_exclude_large_files(self, git_manager, temp_work_dir):
        """Test that large files are excluded"""
        large_file = os.path.join(temp_work_dir, 'large.bin')
        # Create a file larger than threshold
        with open(large_file, 'wb') as f:
            f.write(b'x' * (25 * 1024 * 1024))  # 25 MB
        assert git_manager._should_include_file(large_file, temp_work_dir) is False
    
    def test_collect_files(self, git_manager, temp_work_dir):
        """Test collecting files from directory"""
        # Ensure shadow repo exists before collecting files
        git_manager._ensure_shadow_repo(temp_work_dir)
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert len(files) > 0
        assert 'train.py' in files
        assert 'config.yaml' in files
        assert 'src/model.py' in files


class TestIncludePatterns:
    """Test .scheduler_snapshot_include functionality"""
    
    def test_parse_include_file_basic(self, git_manager, temp_work_dir):
        """Test parsing basic include patterns"""
        include_file = os.path.join(temp_work_dir, '.scheduler_snapshot_include')
        with open(include_file, 'w') as f:
            f.write('large_model.pkl\n')
            f.write('# This is a comment\n')
            f.write('data/*.csv\n')
            f.write('\n')  # Empty line
        
        patterns = git_manager._parse_scheduler_snapshot_include(temp_work_dir)
        assert 'large_model.pkl' in patterns
        assert 'data/*.csv' in patterns
        assert len(patterns) == 2  # Comment and empty line ignored
    
    def test_parse_include_file_no_file(self, git_manager, temp_work_dir):
        """Test parsing when include file doesn't exist"""
        patterns = git_manager._parse_scheduler_snapshot_include(temp_work_dir)
        assert patterns == set()
    
    def test_include_bypasses_size_limits(self, git_manager, temp_work_dir):
        """Test that included files bypass size limits"""
        # Create a large file that would normally be excluded
        large_file = os.path.join(temp_work_dir, 'large_model.pkl')
        with open(large_file, 'wb') as f:
            f.write(b'x' * (25 * 1024 * 1024))  # 25 MB - exceeds default limit
        
        # Create include file
        include_file = os.path.join(temp_work_dir, '.scheduler_snapshot_include')
        with open(include_file, 'w') as f:
            f.write('large_model.pkl\n')
        
        # Collect files - large file should be included
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert 'large_model.pkl' in files
    
    def test_include_glob_patterns(self, git_manager, temp_work_dir):
        """Test that glob patterns in include file work"""
        # Create test files
        os.makedirs(os.path.join(temp_work_dir, 'models'), exist_ok=True)
        with open(os.path.join(temp_work_dir, 'models', 'model1.pkl'), 'w') as f:
            f.write('model1')
        with open(os.path.join(temp_work_dir, 'models', 'model2.pkl'), 'w') as f:
            f.write('model2')
        with open(os.path.join(temp_work_dir, 'models', 'config.txt'), 'w') as f:
            f.write('config')
        
        # Create include file with glob pattern
        include_file = os.path.join(temp_work_dir, '.scheduler_snapshot_include')
        with open(include_file, 'w') as f:
            f.write('models/*.pkl\n')
        
        # Collect files - should include both .pkl files
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert 'models/model1.pkl' in files
        assert 'models/model2.pkl' in files
        # Should not include .txt file
        assert 'models/config.txt' not in files
    
    def test_include_recursive_patterns(self, git_manager, temp_work_dir):
        """Test recursive glob patterns (**/) in include file"""
        # Create nested structure
        os.makedirs(os.path.join(temp_work_dir, 'data', 'train'), exist_ok=True)
        os.makedirs(os.path.join(temp_work_dir, 'data', 'test'), exist_ok=True)
        with open(os.path.join(temp_work_dir, 'data', 'train', 'train.npy'), 'w') as f:
            f.write('train data')
        with open(os.path.join(temp_work_dir, 'data', 'test', 'test.npy'), 'w') as f:
            f.write('test data')
        
        # Create include file with recursive pattern
        include_file = os.path.join(temp_work_dir, '.scheduler_snapshot_include')
        with open(include_file, 'w') as f:
            f.write('data/**/*.npy\n')
        
        # Collect files - should include both files
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        assert 'data/train/train.npy' in files
        assert 'data/test/test.npy' in files


class TestCreateSnapshot:
    """Test create_snapshot method"""
    
    def test_creates_snapshot_successfully(self, git_manager, temp_work_dir):
        """Test successful snapshot creation"""
        result = git_manager.create_snapshot('job123', temp_work_dir)
        
        assert result is not None
        snapshot_ref, workspace_root = result
        assert len(snapshot_ref) == 40  # SHA-1 hash length
        assert workspace_root == temp_work_dir
    
    def test_creates_branch_for_job(self, git_manager, temp_work_dir):
        """Test that a branch is created for the job"""
        job_id = 'job456'
        result = git_manager.create_snapshot(job_id, temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result
        
        # Check branch exists in the workspace's shadow repo
        shadow_repo_path = git_manager._get_shadow_repo_path(workspace_root)
        # .scheduler-git IS the git directory (no .git subfolder)
        git_dir = shadow_repo_path
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'branch', '--list', f'job-{job_id}'],
            cwd=workspace_root,
            stdout=subprocess.PIPE,
            text=True
        )
        assert f'job-{job_id}' in result.stdout
    
    def test_snapshot_contains_files(self, git_manager, temp_work_dir):
        """Test that snapshot contains the expected files"""
        result = git_manager.create_snapshot('job789', temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result
        
        # Get files in the snapshot from workspace's shadow repo
        shadow_repo_path = git_manager._get_shadow_repo_path(workspace_root)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=workspace_root,
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
        
        result = git_manager.create_snapshot('job_nested', temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result
        
        # Verify nested file is in snapshot
        shadow_repo_path = git_manager._get_shadow_repo_path(workspace_root)
        git_dir = shadow_repo_path  # .scheduler-git IS the git directory
        
        result = subprocess.run(
            ['git', f'--git-dir={git_dir}', 'ls-tree', '-r', '--name-only', snapshot_ref],
            cwd=workspace_root,
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
        result = git_manager.create_snapshot('job_restore', temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result
        
        # Restore to a new location
        restore_dir = tempfile.mkdtemp()
        try:
            result = git_manager.restore_snapshot('job_restore', snapshot_ref, workspace_root, restore_dir)
            
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


class TestFolderFileLimits:
    """Test folder file counting and limits"""
    
    def test_folder_count_respects_pattern_filtering(self, git_manager, temp_work_dir):
        """Test that folder file counting only counts files that pass pattern filtering
        
        This is a regression test for a bug where:
        1. git ls-files returned all untracked files
        2. We counted ALL files in git_files for folder limits
        3. But we only checked files in filtered_git_files
        4. Result: folders with many excluded files would hit the limit even for valid files
        """
        # Create a folder with many files that should be excluded
        data_dir = os.path.join(temp_work_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        # Add many .log files (which are in exclude patterns)
        for i in range(150):  # More than default max_files_per_folder (100)
            with open(os.path.join(data_dir, f'log_{i}.log'), 'w') as f:
                f.write(f'log entry {i}\n')
        
        # Add a few .txt files that should be included
        important_files = []
        for i in range(5):
            fname = f'important_{i}.txt'
            important_files.append(f'data/{fname}')
            with open(os.path.join(data_dir, fname), 'w') as f:
                f.write(f'important data {i}\n')
        
        # Ensure shadow repo exists before collecting files
        git_manager._ensure_shadow_repo(temp_work_dir)

        # Collect files - important .txt files should be included
        # even though folder has 155 total files (150 .log + 5 .txt)
        files = git_manager._collect_files_to_snapshot(temp_work_dir)
        
        # All important files should be included
        for important_file in important_files:
            assert important_file in files, f"{important_file} should be included despite many .log files in folder"
        
        # .log files should be excluded
        assert not any('.log' in f for f in files), "No .log files should be included"
    
    def test_folder_limit_applies_to_filtered_files(self, git_manager, temp_work_dir):
        """Test that folder limit applies to files after pattern filtering
        
        Create a folder with exactly max_files_per_folder valid files
        and verify all are included (no premature limiting).
        """
        # Get the max_files_per_folder limit
        max_files = git_manager.max_files_per_folder
        
        # Create a folder with exactly max_files valid Python files
        scripts_dir = os.path.join(temp_work_dir, 'scripts')
        os.makedirs(scripts_dir, exist_ok=True)
        
        for i in range(max_files):
            with open(os.path.join(scripts_dir, f'script_{i}.py'), 'w') as f:
                f.write(f'# script {i}\n')
        
        # Ensure shadow repo exists before collecting files
        git_manager._ensure_shadow_repo(temp_work_dir)

        # Collect files - all should be included
        files = git_manager._collect_files_to_snapshot(temp_work_dir)

        py_files_in_scripts = [f for f in files if f.startswith('scripts/') and f.endswith('.py')]
        assert len(py_files_in_scripts) == max_files, \
            f"Should include all {max_files} Python files in scripts/ folder"


class TestTrackedFiles:
    """Test that tracked git files are included in snapshots"""

    def test_includes_tracked_files(self, git_manager, temp_work_dir):
        """Test that files tracked by git are included in snapshots

        This is a regression test for a bug where only untracked files were
        included in snapshots, causing tracked scripts to be missing when
        jobs were executed on worker nodes.
        """
        # Initialize a real git repository in the temp directory
        subprocess.run(['git', 'init'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_work_dir, check=True)

        # Create and track a script file
        script_file = os.path.join(temp_work_dir, 'eval-23k.sh')
        with open(script_file, 'w') as f:
            f.write('#!/bin/bash\necho "Running evaluation"\n')

        # Add and commit the script to git
        subprocess.run(['git', 'add', 'eval-23k.sh'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'commit', '-m', 'Add evaluation script'], cwd=temp_work_dir, check=True)

        # Create an untracked file too
        untracked_file = os.path.join(temp_work_dir, 'untracked.py')
        with open(untracked_file, 'w') as f:
            f.write('print("untracked")\n')

        # Ensure shadow repo exists before collecting files
        git_manager._ensure_shadow_repo(temp_work_dir)

        # Collect files for snapshot
        files = git_manager._collect_files_to_snapshot(temp_work_dir)

        # Both tracked and untracked files should be included
        assert 'eval-23k.sh' in files, "Tracked script should be included in snapshot"
        assert 'untracked.py' in files, "Untracked file should be included in snapshot"
        assert 'train.py' in files, "Original untracked files should still be included"

    def test_snapshot_with_tracked_files_can_be_restored(self, git_manager, temp_work_dir):
        """Test that snapshots with tracked files can be restored correctly"""
        # Initialize git repo
        subprocess.run(['git', 'init'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test.com'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'config', 'user.name', 'Test User'], cwd=temp_work_dir, check=True)

        # Create and track a script
        script_file = os.path.join(temp_work_dir, 'run.sh')
        with open(script_file, 'w') as f:
            f.write('#!/bin/bash\necho "Running"\n')

        subprocess.run(['git', 'add', 'run.sh'], cwd=temp_work_dir, check=True)
        subprocess.run(['git', 'commit', '-m', 'Add run script'], cwd=temp_work_dir, check=True)

        # Create snapshot
        result = git_manager.create_snapshot('job_tracked', temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result

        # Restore snapshot
        restore_dir = tempfile.mkdtemp()
        try:
            success = git_manager.restore_snapshot('job_tracked', snapshot_ref, workspace_root, restore_dir)
            assert success is True

            # Verify tracked script was restored
            restored_script = os.path.join(restore_dir, 'run.sh')
            assert os.path.exists(restored_script), "Tracked script should be restored"

            with open(restored_script, 'r') as f:
                content = f.read()
            assert 'Running' in content

        finally:
            # Cleanup
            git_manager.cleanup_snapshot('job_tracked', snapshot_ref, workspace_root, restore_dir)


class TestIntegration:
    """Integration tests for complete workflow"""

    def test_complete_workflow(self, git_manager, temp_work_dir):
        """Test complete create -> restore -> cleanup workflow"""
        job_id = 'job_workflow'

        # 1. Create snapshot
        result = git_manager.create_snapshot(job_id, temp_work_dir)
        assert result is not None
        snapshot_ref, workspace_root = result

        # 2. Restore snapshot
        restore_dir = tempfile.mkdtemp()
        success = git_manager.restore_snapshot(job_id, snapshot_ref, workspace_root, restore_dir)
        assert success is True

        # 3. Verify restored files
        assert os.path.exists(os.path.join(restore_dir, 'train.py'))
        with open(os.path.join(restore_dir, 'train.py'), 'r') as f:
            content = f.read()
        assert 'training' in content

        # 4. Cleanup
        git_manager.cleanup_snapshot(job_id, snapshot_ref, workspace_root, restore_dir)

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
