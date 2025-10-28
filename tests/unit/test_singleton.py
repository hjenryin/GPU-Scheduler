"""Unit tests for scheduler.worker.singleton module"""
import os
import json
import pytest
import signal
import tempfile
import time
from unittest.mock import Mock, patch, mock_open
from pathlib import Path

from scheduler.worker.singleton import SingletonDaemon, is_daemon_running


class TestSingletonDaemon:
    """Tests for SingletonDaemon class"""

    @pytest.fixture
    def temp_lockfile(self):
        """Create a temporary lockfile path for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = os.path.join(tmpdir, 'test.lock')
            yield lockfile_path

    @pytest.fixture
    def singleton(self, temp_lockfile):
        """Create a SingletonDaemon instance for testing"""
        return SingletonDaemon(temp_lockfile)

    def test_init(self, temp_lockfile):
        """Test initialization"""
        daemon = SingletonDaemon(temp_lockfile)
        assert daemon.lockfile_path == temp_lockfile
        assert daemon.lockfile is None
        assert isinstance(daemon._original_signal_handlers, dict)

    def test_acquire_lock_creates_directory(self):
        """Test that acquire_lock creates parent directory if needed"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile = os.path.join(tmpdir, 'subdir', 'test.lock')
            daemon = SingletonDaemon(lockfile)
            
            result = daemon.acquire_lock()
            assert result is True
            assert os.path.exists(lockfile)
            daemon.release_lock()

    def test_acquire_lock_success(self, singleton):
        """Test successfully acquiring lock"""
        result = singleton.acquire_lock()
        assert result is True
        assert singleton.lockfile is not None
        assert os.path.exists(singleton.lockfile_path)
        singleton.release_lock()

    def test_acquire_lock_already_exists(self, temp_lockfile):
        """Test acquiring lock when another process has it"""
        # Create first daemon and acquire lock
        daemon1 = SingletonDaemon(temp_lockfile)
        daemon1.acquire_lock()
        
        # Try to acquire lock again (should fail)
        daemon2 = SingletonDaemon(temp_lockfile)
        with patch('scheduler.worker.singleton.os.kill', autospec=True) as mock_kill:
            # Mock kill to simulate process is running
            mock_kill.return_value = None  # os.kill(pid, 0) doesn't raise when process exists
            result = daemon2.acquire_lock()
            assert result is False
        
        daemon1.release_lock()

    def test_acquire_lock_stale_lockfile(self, temp_lockfile):
        """Test acquiring lock when lockfile exists but process is dead"""
        # Create stale lockfile with non-existent PID
        with open(temp_lockfile, 'w') as f:
            json.dump({'pid': 99999}, f)
        
        daemon = SingletonDaemon(temp_lockfile)
        with patch('scheduler.worker.singleton.os.kill', autospec=True) as mock_kill:
            # Mock kill to simulate process not found
            mock_kill.side_effect = OSError()  # Process doesn't exist
            result = daemon.acquire_lock()
            assert result is True  # Should clean up stale lock and acquire
        
        daemon.release_lock()

    def test_acquire_lock_invalid_json(self, temp_lockfile):
        """Test acquiring lock when lockfile has invalid JSON"""
        # Create invalid lockfile
        with open(temp_lockfile, 'w') as f:
            f.write('invalid json')
        
        daemon = SingletonDaemon(temp_lockfile)
        result = daemon.acquire_lock()
        assert result is True  # Should clean up invalid lock and acquire
        
        daemon.release_lock()

    def test_acquire_lock_missing_pid(self, temp_lockfile):
        """Test acquiring lock when lockfile is missing PID"""
        # Create lockfile without PID
        with open(temp_lockfile, 'w') as f:
            json.dump({'other': 'data'}, f)
        
        daemon = SingletonDaemon(temp_lockfile)
        result = daemon.acquire_lock()
        assert result is True  # Should clean up invalid lock and acquire
        
        daemon.release_lock()

    def test_release_lock(self, singleton):
        """Test releasing lock"""
        singleton.acquire_lock()
        assert os.path.exists(singleton.lockfile_path)
        
        singleton.release_lock()
        assert not os.path.exists(singleton.lockfile_path)
        assert singleton.lockfile is None

    def test_release_lock_not_acquired(self, singleton):
        """Test releasing lock when not acquired"""
        singleton.release_lock()  # Should not raise

    def test_release_lock_with_exception(self, singleton):
        """Test releasing lock when file close raises exception"""
        singleton.acquire_lock()
        
        with patch('scheduler.worker.singleton.os.close', side_effect=OSError("test error"), autospec=True):
            # Should not raise
            singleton.release_lock()

    def test_context_manager_success(self, singleton):
        """Test using singleton as context manager"""
        with singleton:
            assert os.path.exists(singleton.lockfile_path)
        assert not os.path.exists(singleton.lockfile_path)

    def test_context_manager_lock_failed(self, temp_lockfile):
        """Test using singleton as context manager when lock fails"""
        daemon1 = SingletonDaemon(temp_lockfile)
        daemon1.acquire_lock()
        
        daemon2 = SingletonDaemon(temp_lockfile)
        with patch('scheduler.worker.singleton.os.kill', autospec=True) as mock_kill:
            mock_kill.return_value = None
            
            with pytest.raises(RuntimeError, match="Failed to acquire singleton lock"):
                with daemon2:
                    pass
        
        daemon1.release_lock()

    def test_setup_signal_handlers(self, singleton):
        """Test signal handler setup"""
        # Signal handlers should be set up during init
        assert signal.SIGTERM in singleton._original_signal_handlers
        assert signal.SIGINT in singleton._original_signal_handlers

    def test_restore_signal_handlers(self, singleton):
        """Test restoring signal handlers"""
        singleton.release_lock()
        # Should not raise

    def test_signal_handler_cleanup(self, singleton):
        """Test signal handler calls cleanup"""
        singleton.acquire_lock()
        
        # Simulate signal handler being called
        with patch('scheduler.worker.singleton.os.kill', autospec=True) as mock_kill:
            with patch('scheduler.worker.singleton.logger', autospec=True) as mock_logger:
                # Call the cleanup handler
                cleanup_handler = singleton._original_signal_handlers.get(signal.SIGTERM)
                if cleanup_handler and hasattr(cleanup_handler, '__wrapped__'):
                    # Get the actual handler
                    cleanup_handler(1, None)
        
        singleton.release_lock()


class TestIsDaemonRunning:
    """Tests for is_daemon_running function"""

    @pytest.fixture
    def temp_lockfile(self):
        """Create a temporary lockfile path for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lockfile_path = os.path.join(tmpdir, 'test.lock')
            yield lockfile_path

    def test_not_running_no_lockfile(self, temp_lockfile):
        """Test when lockfile doesn't exist"""
        assert is_daemon_running(temp_lockfile) is False

    def test_running_with_valid_pid(self, temp_lockfile):
        """Test when lockfile exists with valid running PID"""
        # Create lockfile with current PID
        with open(temp_lockfile, 'w') as f:
            json.dump({'pid': os.getpid()}, f)
        
        assert is_daemon_running(temp_lockfile) is True

    def test_stale_lockfile_dead_pid(self, temp_lockfile):
        """Test when lockfile exists but process is dead"""
        with open(temp_lockfile, 'w') as f:
            json.dump({'pid': 99999}, f)
        
        assert is_daemon_running(temp_lockfile) is False

    def test_invalid_json(self, temp_lockfile):
        """Test when lockfile has invalid JSON"""
        with open(temp_lockfile, 'w') as f:
            f.write('invalid json')
        
        assert is_daemon_running(temp_lockfile) is False

    def test_missing_pid(self, temp_lockfile):
        """Test when lockfile is missing PID"""
        with open(temp_lockfile, 'w') as f:
            json.dump({'other': 'data'}, f)
        
        assert is_daemon_running(temp_lockfile) is False

    def test_missing_file_after_check(self, temp_lockfile):
        """Test when lockfile is removed between checks"""
        with patch('scheduler.worker.singleton.os.path.exists', return_value=False, autospec=True):
            assert is_daemon_running(temp_lockfile) is False

