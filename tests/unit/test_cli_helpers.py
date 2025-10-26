"""Unit tests for CLI helper functions"""
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from scheduler.cli.helpers import check_head_address_or_prompt


class TestCLIHelpers:
    """Tests for CLI helper functions"""

    @patch('scheduler.cli.helpers.load_head_info')
    def test_check_head_address_available(self, mock_load_head_info):
        """Test check_head_address_or_prompt returns True when address available"""
        mock_load_head_info.return_value = "localhost:8265"
        
        result = check_head_address_or_prompt()
        
        assert result is True
        mock_load_head_info.assert_called_once()

    @patch('scheduler.cli.helpers.load_head_info')
    @patch('scheduler.cli.helpers.click.echo')
    def test_check_head_address_not_available(self, mock_echo, mock_load_head_info):
        """Test check_head_address_or_prompt returns False and shows message when address not available"""
        mock_load_head_info.return_value = None
        
        result = check_head_address_or_prompt()
        
        assert result is False
        assert mock_echo.call_count >= 3  # Multiple messages shown
        # Check that error message and instructions are shown
        calls = [call[0][0] for call in mock_echo.call_args_list]
        assert any("Error" in msg or "❌" in msg for msg in calls)
        assert any("start" in msg.lower() for msg in calls)

    @patch('scheduler.cli.helpers.load_head_info')
    @patch('scheduler.cli.helpers.click.echo')
    def test_check_head_address_empty_string(self, mock_echo, mock_load_head_info):
        """Test check_head_address_or_prompt returns False for empty string"""
        mock_load_head_info.return_value = ""
        
        result = check_head_address_or_prompt()
        
        assert result is False
        mock_echo.assert_called()
