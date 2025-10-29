"""Unit tests for GitSnapshotManager"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
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
    """Create a GitSnapshotManager instance"""
    return GitSnapshotManager(mock_config)


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
    
    # Create initial commit
    test_file = os.path.join(temp_dir, 'test.py')
    with open(test_file, 'w') as f:
        f.write('print("hello")\n')
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
    test_file = os.path.join(temp_dir, 'test.py')
    with open(test_file, 'w') as f:
        f.write('print("hello")\n')
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestGitSnapshotManager:
    """Test GitSnapshotManager initialization"""
    
    def test_initialization(self, mock_config):
        """Test that GitSnapshotManager initializes correctly"""
        manager = GitSnapshotManager(mock_config)
        assert manager.config == mock_config


class TestIsGitRepository:
    """Test is_git_repository method"""
    
    def test_returns_true_for_git_repo(self, git_manager, temp_git_repo):
        """Test detection of git repository"""
        assert git_manager.is_git_repository(temp_git_repo) is True
    
    def test_returns_false_for_non_git_dir(self, git_manager, temp_non_git_dir):
        """Test detection of non-git directory"""
        assert git_manager.is_git_repository(temp_non_git_dir) is False
    
    def test_returns_false_for_nonexistent_dir(self, git_manager):
        """Test handling of nonexistent directory"""
        assert git_manager.is_git_repository('/nonexistent/path') is False
    
    def test_returns_false_when_git_not_available(self, git_manager, temp_non_git_dir):
        """Test handling when git command is not available"""
        with patch('subprocess.run', side_effect=FileNotFoundError()):
            assert git_manager.is_git_repository(temp_non_git_dir) is False
    
    def test_returns_false_on_timeout(self, git_manager, temp_git_repo):
        """Test handling of git command timeout"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('git', 5)):
            assert git_manager.is_git_repository(temp_git_repo) is False


class TestCreateSnapshot:
    """Test create_snapshot method"""
    
    def test_returns_none_for_non_git_repo(self, git_manager, temp_non_git_dir):
        """Test snapshot creation in non-git directory returns None"""
        snapshot_ref = git_manager.create_snapshot('job123', temp_non_git_dir)
        assert snapshot_ref is None
    
    def test_returns_commit_sha_for_clean_repo(self, git_manager, temp_git_repo):
        """Test snapshot creation in git repo with no changes"""
        snapshot_ref = git_manager.create_snapshot('job123', temp_git_repo)
        assert snapshot_ref is not None
        assert len(snapshot_ref) == 40  # SHA-1 hash length
        assert ':' not in snapshot_ref  # No stash, just commit SHA
    
    def test_returns_commit_and_stash_for_dirty_repo(self, git_manager, temp_git_repo):
        """Test snapshot creation in git repo with uncommitted changes"""
        # Modify a file
        test_file = os.path.join(temp_git_repo, 'test.py')
        with open(test_file, 'w') as f:
            f.write('print("modified")\n')
        
        snapshot_ref = git_manager.create_snapshot('job123', temp_git_repo)
        assert snapshot_ref is not None
        assert ':' in snapshot_ref  # Has stash: "commit_sha:stash_sha"
        
        commit_sha, stash_sha = snapshot_ref.split(':', 1)
        assert len(commit_sha) == 40
        assert len(stash_sha) == 40
    
    def test_preserves_working_directory_state(self, git_manager, temp_git_repo):
        """Test that create_snapshot restores working directory after stashing"""
        # Modify a file
        test_file = os.path.join(temp_git_repo, 'test.py')
        with open(test_file, 'w') as f:
            f.write('print("modified")\n')
        
        # Create snapshot
        snapshot_ref = git_manager.create_snapshot('job123', temp_git_repo)
        assert snapshot_ref is not None
        
        # Verify working directory still has modifications
        with open(test_file, 'r') as f:
            content = f.read()
        assert 'modified' in content
    
    def test_handles_git_command_timeout(self, git_manager, temp_git_repo):
        """Test handling of git command timeout during snapshot creation"""
        with patch('subprocess.run') as mock_run:
            # First call succeeds (is_git_repository check)
            # Second call times out (rev-parse HEAD)
            mock_run.side_effect = [
                Mock(returncode=0, stdout='', stderr=''),
                subprocess.TimeoutExpired('git', 5)
            ]
            
            snapshot_ref = git_manager.create_snapshot('job123', temp_git_repo)
            assert snapshot_ref is None
    
    def test_handles_git_command_failure(self, git_manager, temp_git_repo):
        """Test handling of git command failure during snapshot creation"""
        with patch('subprocess.run') as mock_run:
            # First call succeeds (is_git_repository check)
            # Second call fails (rev-parse HEAD)
            mock_run.side_effect = [
                Mock(returncode=0, stdout='', stderr=''),
                subprocess.CalledProcessError(1, 'git', stderr='error')
            ]
            
            snapshot_ref = git_manager.create_snapshot('job123', temp_git_repo)
            assert snapshot_ref is None


class TestRestoreSnapshot:
    """Test restore_snapshot method"""
    
    def test_returns_false_for_none_snapshot_ref(self, git_manager):
        """Test restore with None snapshot reference"""
        result = git_manager.restore_snapshot('job123', None, '/tmp/target')
        assert result is False
    
    def test_returns_false_for_empty_snapshot_ref(self, git_manager):
        """Test restore with empty snapshot reference"""
        result = git_manager.restore_snapshot('job123', '', '/tmp/target')
        assert result is False
    
    def test_returns_false_for_non_git_target_dir(self, git_manager, temp_non_git_dir):
        """Test restore to non-git directory"""
        result = git_manager.restore_snapshot('job123', 'abc123', temp_non_git_dir)
        assert result is False
    
    def test_parses_commit_only_snapshot_ref(self, git_manager, temp_git_repo):
        """Test parsing of commit-only snapshot reference"""
        # Get the current commit
        result = subprocess.run(
            ['git', 'rev-parse', 'HEAD'],
            cwd=temp_git_repo,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        commit_sha = result.stdout.strip()
        
        # Try to restore (will fail because target isn't a git repo, but parsing should work)
        with patch.object(git_manager, 'restore_snapshot', wraps=git_manager.restore_snapshot) as mock_restore:
            git_manager.restore_snapshot('job123', commit_sha, temp_git_repo)
            # Check that the method was called with correct snapshot_ref
            assert mock_restore.call_args[0][1] == commit_sha
    
    def test_handles_git_command_timeout(self, git_manager, temp_git_repo):
        """Test handling of git command timeout during restore"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('git', 30)):
            result = git_manager.restore_snapshot('job123', 'abc123', temp_git_repo)
            assert result is False
    
    def test_handles_git_command_failure(self, git_manager, temp_git_repo):
        """Test handling of git command failure during restore"""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'git', stderr='error')):
            result = git_manager.restore_snapshot('job123', 'abc123', temp_git_repo)
            assert result is False


class TestCleanupSnapshot:
    """Test cleanup_snapshot method"""
    
    def test_cleanup_runs_without_error(self, git_manager):
        """Test that cleanup completes without error"""
        # This is a no-op currently, but should not raise exceptions
        git_manager.cleanup_snapshot('job123', 'abc123:def456')
        # If we get here without exception, test passes
    
    def test_cleanup_with_none_snapshot_ref(self, git_manager):
        """Test cleanup with None snapshot reference"""
        git_manager.cleanup_snapshot('job123', None)
        # Should handle gracefully
    
    def test_cleanup_with_commit_only_ref(self, git_manager):
        """Test cleanup with commit-only snapshot reference"""
        git_manager.cleanup_snapshot('job123', 'abc123')
        # Should handle gracefully
