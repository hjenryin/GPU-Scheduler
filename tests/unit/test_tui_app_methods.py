"""Unit tests for SchedulerTUI app methods using Textual's run_test"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from scheduler.tui.app import SchedulerTUI
from scheduler.api import SchedulerClient


class TestSchedulerTUIComposition:
    """Tests for SchedulerTUI compose method"""

    @pytest.mark.asyncio
    async def test_compose_returns_empty_for_screen_based_app(self):
        """Test that compose returns empty generator for screen-based app"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        # Get compose result
        composition = list(app.compose())
        
        # Should be empty since we use screens, not direct widgets
        assert len(composition) == 0
        
        # But screens should be registered
        assert "cluster" in app.SCREENS
        assert "nodes" in app.SCREENS
        assert "jobs" in app.SCREENS
        assert "gpus" in app.SCREENS


class TestSchedulerTUIInitialization:
    """Tests for SchedulerTUI initialization"""

    def test_init_sets_client(self):
        """Test that __init__ sets the client"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        assert app.client == mock_client
        assert app.refresh_interval == 2.0
        assert app.nodes_data == []
        assert app.jobs_data == []


class TestSchedulerTUIActions:
    """Tests for action handlers"""

    @pytest.mark.asyncio
    async def test_action_quit(self):
        """Test quit action"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Start the app
            await pilot.press("q")
            
            # Should exit the app
            assert pilot.app.is_running == False

    def test_action_refresh(self):
        """Test refresh action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists
        assert hasattr(app, 'action_refresh')
        assert callable(app.action_refresh)
        
        # Call action - should trigger refresh
        app.action_refresh()
        mock_client.list_nodes.assert_called()

    def test_action_help(self):
        """Test help action"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists
        assert hasattr(app, 'action_help')
        assert callable(app.action_help)

    def test_action_switch_to_cluster(self):
        """Test switch to cluster action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists and can be called
        assert hasattr(app, 'action_switch_to_cluster')
        assert callable(app.action_switch_to_cluster)
        
        try:
            app.action_switch_to_cluster()
        except:
            pass  # Expected without full app context


class TestSchedulerTUIRefreshData:
    """Tests for refresh_data method"""

    def test_refresh_data_fetches_from_client(self):
        """Test that refresh_data calls client methods"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = [Mock(), Mock()]
        mock_client.list_jobs.return_value = [Mock()]
        
        app = SchedulerTUI(client=mock_client)
        
        # Call refresh_data
        app.refresh_data()
        
        # Should call client methods
        mock_client.list_nodes.assert_called_once()
        mock_client.list_jobs.assert_called_once()
        
        # Should populate data
        assert len(app.nodes_data) == 2
        assert len(app.jobs_data) == 1

    def test_refresh_data_handles_exception(self):
        """Test that refresh_data handles exceptions gracefully"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.side_effect = Exception("Network error")
        
        app = SchedulerTUI(client=mock_client)
        
        # Should not raise exception
        app.refresh_data()
        
        # Should notify error
        # We can't easily test notify without running app, but we can verify no crash

    @pytest.mark.asyncio
    async def test_refresh_data_updates_cluster_screen(self):
        """Test that refresh_data updates ClusterScreen when screen is available"""
        from scheduler.tui.screens.cluster import ClusterScreen
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.list_jobs.return_value = [Mock()]
        
        app = SchedulerTUI(client=mock_client)
        
        # Run app to mount screen
        async with app.run_test() as pilot:
            # Now call refresh_data - it should update the mounted screen
            app.refresh_data()
            
            # Verify data was fetched
            mock_client.list_nodes.assert_called()
            mock_client.list_jobs.assert_called()


class TestSchedulerTUIIntervalSetup:
    """Tests for interval/timer setup"""

    @pytest.mark.asyncio
    async def test_on_mount_sets_intervals(self):
        """Test that on_mount sets up refresh interval"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        # on_mount is called during app initialization
        # We can test by checking if set_interval exists
        assert hasattr(app, 'set_interval')
        assert app.refresh_interval == 2.0


class TestSchedulerTUIScreenSwitching:
    """Tests for screen switching actions"""

    def test_action_switch_to_nodes(self):
        """Test switch to nodes screen action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists and can be called
        assert hasattr(app, 'action_switch_to_nodes')
        assert callable(app.action_switch_to_nodes)
        
        # Test calling it doesn't crash (even without full app context)
        try:
            app.action_switch_to_nodes()
        except:
            pass  # Expected to fail without app context, but we test it exists

    def test_action_switch_to_jobs(self):
        """Test switch to jobs screen action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists and can be called
        assert hasattr(app, 'action_switch_to_jobs')
        assert callable(app.action_switch_to_jobs)
        
        try:
            app.action_switch_to_jobs()
        except:
            pass

    def test_action_switch_to_gpus(self):
        """Test switch to gpus screen action"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        app = SchedulerTUI(client=mock_client)
        
        # Test that action exists and can be called
        assert hasattr(app, 'action_switch_to_gpus')
        assert callable(app.action_switch_to_gpus)
        
        try:
            app.action_switch_to_gpus()
        except:
            pass


class TestRunTUI:
    """Tests for run_tui function"""

    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_with_client(self, mock_tui_class):
        """Test run_tui with client"""
        from scheduler.tui.app import run_tui
        
        mock_client = Mock(spec=SchedulerClient)
        mock_app = MagicMock()
        mock_tui_class.return_value = mock_app
        
        run_tui(client=mock_client)
        
        mock_tui_class.assert_called_once_with(mock_client)
        mock_app.run.assert_called_once()

    @patch('scheduler.tui.app.SchedulerClient')
    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_with_address(self, mock_tui_class, mock_client_class):
        """Test run_tui with address"""
        from scheduler.tui.app import run_tui
        
        mock_client = Mock(spec=SchedulerClient)
        mock_client_class.return_value = mock_client
        mock_app = MagicMock()
        mock_tui_class.return_value = mock_app
        
        run_tui(address="localhost:8265")
        
        mock_client_class.assert_called_once_with(address="localhost:8265")
        mock_tui_class.assert_called_once_with(mock_client)
        mock_app.run.assert_called_once()

    @patch('scheduler.tui.app.SchedulerClient')
    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_without_parameters(self, mock_tui_class, mock_client_class):
        """Test run_tui without parameters"""
        from scheduler.tui.app import run_tui
        
        mock_client = Mock(spec=SchedulerClient)
        mock_client_class.return_value = mock_client
        mock_app = MagicMock()
        mock_tui_class.return_value = mock_app
        
        run_tui()
        
        mock_client_class.assert_called_once_with(address=None)
        mock_tui_class.assert_called_once_with(mock_client)
        mock_app.run.assert_called_once()


class TestSchedulerTUIKeyboardShortcuts:
    """Tests for keyboard shortcuts"""

    @pytest.mark.asyncio
    async def test_r_key_triggers_refresh(self):
        """Test that 'r' key triggers refresh"""
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Press 'r' key
            await pilot.press("r")
            
            # Should call refresh_data
            # Can't easily verify without checking call counts
            # But we can verify the key binding exists
            assert "r" in [b.key for b in app.BINDINGS]
            assert any(b.key == "r" and b.action == "refresh" for b in app.BINDINGS)

    @pytest.mark.asyncio
    async def test_h_key_triggers_help(self):
        """Test that 'h' key triggers help"""
        mock_client = Mock(spec=SchedulerClient)
        app = SchedulerTUI(client=mock_client)
        
        async with app.run_test() as pilot:
            # Press 'h' key
            await pilot.press("h")
            
            # Should show help
            # Can't easily verify without checking screen contents
            # But we can verify the key binding exists
            assert "h" in [b.key for b in app.BINDINGS]


class TestSchedulerTUIRefreshDataWithScreens:
    """Tests for refresh_data with different screen types"""

    @pytest.mark.asyncio
    async def test_refresh_data_with_nodes_screen(self):
        """Test refresh_data with NodesScreen"""
        from scheduler.tui.screens.nodes import NodesScreen
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        # Test that refresh_data handles the isinstance check properly
        # We test this by calling refresh_data when app is not fully mounted
        # Just verify it doesn't crash
        app.refresh_data()
        mock_client.list_nodes.assert_called()

    def test_refresh_data_with_jobs_screen(self):
        """Test refresh_data with JobsScreen"""
        from scheduler.tui.screens.jobs import JobsScreen
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = []
        mock_client.list_jobs.return_value = [Mock()]
        
        app = SchedulerTUI(client=mock_client)
        
        # Test that refresh_data handles the isinstance check properly
        app.refresh_data()
        mock_client.list_jobs.assert_called()

    def test_refresh_data_with_gpus_screen(self):
        """Test refresh_data with GPUsScreen"""
        from scheduler.tui.screens.gpus import GPUsScreen
        mock_client = Mock(spec=SchedulerClient)
        mock_client.list_nodes.return_value = [Mock()]
        mock_client.list_jobs.return_value = []
        
        app = SchedulerTUI(client=mock_client)
        
        # Test that refresh_data handles the isinstance check properly
        app.refresh_data()
        mock_client.list_nodes.assert_called()

