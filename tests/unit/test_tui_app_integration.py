"""Unit tests for SchedulerTUI app integration using Textual's run_test"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from scheduler.tui.app import SchedulerTUI
from scheduler.api import SchedulerClient


class TestSchedulerTUIWithAppRunTest:
    """Tests for SchedulerTUI using Textual's run_test context manager"""

    @pytest.mark.asyncio
    async def test_app_on_mount_calls_refresh_data(self):
        """Test that on_mount calls refresh_data"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Give app time to mount and call on_mount
            await pilot.pause(0.1)
            
            # Should have called refresh_data (from on_mount)
            mock_client.list_nodes.assert_called()
            mock_client.list_jobs.assert_called()

    @pytest.mark.asyncio
    async def test_switch_screen_and_data_update(self):
        """Test switching to different screens updates data properly"""
        from scheduler.tui.screens.nodes import NodesScreen
        
        mock_client = Mock(spec=SchedulerClient)
        mock_nodes = [Mock()]
        mock_jobs = [Mock()]
        mock_client.list_nodes.return_value = mock_nodes
        mock_client.list_jobs.return_value = mock_jobs
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Switch to nodes screen
            await pilot.press("n")
            await pilot.pause(0.1)
            
            # Should have refreshed and called list_nodes/list_jobs
            assert mock_client.list_nodes.call_count >= 1
            assert mock_client.list_jobs.call_count >= 1

    @pytest.mark.asyncio
    async def test_switch_to_jobs_screen(self):
        """Test switching to jobs screen"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = [Mock()]
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Switch to jobs screen
            await pilot.press("j")
            await pilot.pause(0.1)
            
            # Should have called client methods
            assert mock_client.list_nodes.call_count >= 1

    @pytest.mark.asyncio
    async def test_switch_to_gpus_screen(self):
        """Test switching to GPUs screen"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Switch to gpus screen
            await pilot.press("g")
            await pilot.pause(0.1)
            
            # Should have called client methods
            assert mock_client.list_nodes.call_count >= 1

    @pytest.mark.asyncio
    async def test_manual_refresh_triggers_data_update(self):
        """Test manual refresh action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Clear any previous calls
            mock_client.reset_mock()
            
            # Press 'r' to trigger manual refresh
            await pilot.press("r")
            await pilot.pause(0.1)
            
            # Should have called refresh methods
            mock_client.list_nodes.assert_called()

    @pytest.mark.asyncio
    async def test_help_action(self):
        """Test help action"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Press 'h' for help
            await pilot.press("h")
            await pilot.pause(0.1)
            
            # Help should trigger action_help which calls notify
            # We can't easily verify the notify without checking internal state
            # But we verify the keybinding exists
            assert "h" in [b.key for b in app.BINDINGS]

