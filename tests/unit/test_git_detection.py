"""Unit tests for git repository detection"""
import os
import tempfile
import subprocess
import shutil
import pytest
from scheduler.worker.git_snapshot import GitSnapshotManager
from scheduler.core.config import Config
from unittest.mock import create_autospec


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    return create_autospec(Config, instance=True, spec_set=True)


@pytest.fixture
def git_manager(mock_config):
    """Create a GitSnapshotManager instance"""
    return GitSnapshotManager(mock_config)


class TestGitDetection:
    """Test git repository detection"""
    
    def test_detects_git_repo(self, git_manager):
        """Test that git repository is detected when .git exists"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Should detect git repo
            assert git_manager.is_git_repository(temp_dir) is True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_detects_non_git_dir(self, git_manager):
        """Test that non-git directory is detected correctly"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Should not detect git repo
            assert git_manager.is_git_repository(temp_dir) is False
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_detects_git_repo_in_subdirectory(self, git_manager):
        """Test that git repo is detected when checking a subdirectory"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Create subdirectory
            subdir = os.path.join(temp_dir, 'subdir')
            os.makedirs(subdir)
            
            # Should detect git repo even in subdirectory
            assert git_manager.is_git_repository(subdir) is True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_detects_git_repo_nested_subdirectory(self, git_manager):
        """Test that git repo is detected in deeply nested subdirectories"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Initialize git repo
            subprocess.run(['git', 'init'], cwd=temp_dir, check=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # Create nested subdirectory
            nested_dir = os.path.join(temp_dir, 'a', 'b', 'c')
            os.makedirs(nested_dir)
            
            # Should detect git repo in nested directory
            assert git_manager.is_git_repository(nested_dir) is True
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
