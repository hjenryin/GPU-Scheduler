"""Unit tests for scheduler.core.head_info module"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, mock_open, MagicMock
from scheduler.core.head_info import save_head_info, load_head_info, clear_head_info


class TestSaveHeadInfo:
    """Tests for save_head_info function"""

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('builtins.open', autospec=True)
    @patch('json.dump', autospec=True)
    def test_save_head_info_updates_lockfile(self, mock_json_dump, mock_open, mock_listdir, mock_exists):
        """Test saving head info updates worker lockfile"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            # Mock reading existing lock file
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_file.read.return_value = '{"pid": 12345}'
            
            save_head_info("localhost:8265")
            
            # Verify json.dump was called with updated data
            mock_json_dump.assert_called()
            call_args = mock_json_dump.call_args[0][0]
            assert call_args['pid'] == 12345
            assert call_args['address'] == "localhost:8265"

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    def test_save_head_info_no_scheduler_dir(self, mock_exists):
        """Test saving head info when scheduler directory doesn't exist"""
        mock_exists.return_value = False
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            # Should not raise exception
            save_head_info("localhost:8265")

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    def test_save_head_info_no_lock_files(self, mock_listdir, mock_exists):
        """Test saving head info when no lock files exist"""
        mock_exists.return_value = True
        mock_listdir.return_value = []
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            # Should not raise exception
            save_head_info("localhost:8265")

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_save_head_info_invalid_lock_file(self, mock_open, mock_listdir, mock_exists):
        """Test saving head info with invalid lock file"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        mock_open.side_effect = Exception("Invalid file")
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            # Should not raise exception, just log warning
            save_head_info("localhost:8265")

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('builtins.open', autospec=True)
    @patch('json.load', autospec=True)
    def test_save_head_info_no_pid_in_lockfile(self, mock_json_load, mock_open, mock_listdir, mock_exists):
        """Test saving head info when lock file has no PID"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_json_load.return_value = {}  # No PID
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            save_head_info("localhost:8265")
            # Should not update the file


class TestLoadHeadInfo:
    """Tests for load_head_info function"""

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    def test_load_head_info_no_scheduler_dir(self, mock_exists):
        """Test loading head info when scheduler directory doesn't exist"""
        mock_exists.return_value = False
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result is None

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    def test_load_head_info_no_lock_files(self, mock_listdir, mock_exists):
        """Test loading head info when no lock files exist"""
        mock_exists.return_value = True
        mock_listdir.return_value = []
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result is None

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('scheduler.core.head_info.os.kill', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_load_head_info_success(self, mock_open, mock_kill, mock_listdir, mock_exists):
        """Test loading head info successfully"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        
        # Mock reading lock file
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = '{"pid": 12345, "address": "localhost:8265"}'
        
        # Mock process check
        mock_kill.return_value = None  # Process exists
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result == "localhost:8265"

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('scheduler.core.head_info.os.kill', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_load_head_info_process_not_running(self, mock_open, mock_kill, mock_listdir, mock_exists):
        """Test loading head info when process is not running"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        
        # Mock reading lock file
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = '{"pid": 12345, "address": "localhost:8265"}'
        
        # Mock process check - process not found (OSError from os.kill)
        mock_kill.side_effect = OSError()
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result is None  # Should return None when process not running

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_load_head_info_invalid_json(self, mock_open, mock_listdir, mock_exists):
        """Test loading head info with invalid JSON"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        mock_open.side_effect = Exception("Invalid JSON")
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result is None

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('scheduler.core.head_info.os.kill', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_load_head_info_no_address(self, mock_open, mock_kill, mock_listdir, mock_exists):
        """Test loading head info when lock file has no address"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']
        
        # Mock reading lock file without address
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = '{"pid": 12345}'
        
        # Mock process check
        mock_kill.return_value = None
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result is None  # No address in lock file

    @patch('scheduler.core.head_info.os.path.exists', autospec=True)
    @patch('scheduler.core.head_info.os.listdir', autospec=True)
    @patch('scheduler.core.head_info.os.kill', autospec=True)
    @patch('builtins.open', autospec=True)
    def test_load_head_info_multiple_workers(self, mock_open, mock_kill, mock_listdir, mock_exists):
        """Test loading head info with multiple worker lock files"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock', 'worker-node2.lock']
        
        # Mock reading first lock file successfully
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = '{"pid": 12345, "address": "localhost:8265"}'
        
        # Mock process check
        mock_kill.return_value = None
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler', autospec=True):
            result = load_head_info()
            assert result == "localhost:8265"

