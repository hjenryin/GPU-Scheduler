"""Additional unit tests for scheduler.core.head_info module - clear_head_info function"""
import pytest
from unittest.mock import patch, MagicMock
from scheduler.core.head_info import clear_head_info


class TestClearHeadInfo:
    """Tests for clear_head_info function"""

    @patch('scheduler.core.head_info.os.path.exists')
    def test_clear_head_info_no_scheduler_dir(self, mock_exists):
        """Test clearing head info when scheduler directory doesn't exist"""
        mock_exists.return_value = False
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler'):
            # Should not raise exception
            clear_head_info()

    @patch('scheduler.core.head_info.os.path.exists')
    @patch('scheduler.core.head_info.os.listdir')
    @patch('scheduler.core.head_info.os.remove')
    def test_clear_head_info_removes_info_files(self, mock_remove, mock_listdir, mock_exists):
        """Test clearing head info removes info files"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.info']
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler'):
            clear_head_info()
            mock_remove.assert_called_once()

    @patch('scheduler.core.head_info.os.path.exists')
    @patch('scheduler.core.head_info.os.listdir')
    @patch('scheduler.core.head_info.os.remove')
    def test_clear_head_info_handles_removal_error(self, mock_remove, mock_listdir, mock_exists):
        """Test clearing head info handles removal errors"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.info']
        mock_remove.side_effect = Exception("Permission denied")
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler'):
            # Should not raise exception, just log warning
            clear_head_info()

    @patch('scheduler.core.head_info.os.path.exists')
    @patch('scheduler.core.head_info.os.listdir')
    def test_clear_head_info_no_info_files(self, mock_listdir, mock_exists):
        """Test clearing head info when no info files exist"""
        mock_exists.return_value = True
        mock_listdir.return_value = ['worker-node1.lock']  # No .info files
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler'):
            # Should not raise exception
            clear_head_info()

    @patch('scheduler.core.head_info.os.path.exists')
    @patch('scheduler.core.head_info.os.listdir')
    def test_clear_head_info_handles_generic_error(self, mock_listdir, mock_exists):
        """Test clearing head info handles generic errors"""
        mock_exists.return_value = True
        mock_listdir.side_effect = Exception("Directory error")
        
        with patch('scheduler.core.head_info.os.path.expanduser', return_value='/tmp/.scheduler'):
            # Should not raise exception, just log error
            clear_head_info()

