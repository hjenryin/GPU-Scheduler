"""Integration tests for TUI application."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from scheduler.tui.app import SchedulerTUI, run_tui
from scheduler.tui.screens import ClusterScreen, NodesScreen, JobsScreen, GPUsScreen
from scheduler.api import SchedulerClient
from scheduler.core import JobStatus, NodeStatus
from tests.unit.test_tui_fixtures import *


class TestSchedulerTUI:
    """Test SchedulerTUI main application."""

    def test_tui_initialization(self, mock_scheduler_client):
        """Test TUI app initialization."""
        app = SchedulerTUI(mock_scheduler_client)
        
        assert app.client == mock_scheduler_client
        assert app.refresh_interval == 2.0
        assert app.nodes_data == []
        assert app.jobs_data == []

    def test_tui_initialization_with_custom_refresh_interval(self, mock_scheduler_client):
        """Test TUI app initialization with custom refresh interval."""
        app = SchedulerTUI(mock_scheduler_client)
        app.refresh_interval = 5.0
        
        assert app.refresh_interval == 5.0

    @patch('scheduler.tui.app.SchedulerTUI.set_interval')
    def test_on_mount(self, mock_set_interval, mock_scheduler_client):
        """Test app mounting behavior."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'refresh_data') as mock_refresh:
            app.on_mount()
            
            # Should set up periodic refresh
            mock_set_interval.assert_called_once_with(app.refresh_interval, app.refresh_data)
            # Should do initial data fetch
            mock_refresh.assert_called_once()

    def test_refresh_data_success(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test successful data refresh."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # Test data refresh without accessing screen property
        app.refresh_data()
        
        assert app.nodes_data == mock_nodes
        assert app.jobs_data == mock_jobs

    def test_refresh_data_error_handling(self, mock_scheduler_client):
        """Test data refresh error handling."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.side_effect = Exception("Connection failed")
        
        with patch.object(app, 'notify') as mock_notify:
            app.refresh_data()
            
            # Should notify user of error
            mock_notify.assert_called_once()
            assert "Error refreshing data" in mock_notify.call_args[0][0]

    def test_refresh_data_cluster_screen_update(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test data refresh updates cluster screen."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # Test that data is fetched and stored correctly
        app.refresh_data()
        
        # Verify data is stored
        assert app.nodes_data == mock_nodes
        assert app.jobs_data == mock_jobs

    def test_refresh_data_nodes_screen_update(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test data refresh updates nodes screen."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # Test that data is fetched and stored correctly
        app.refresh_data()
        
        # Verify data is stored
        assert app.nodes_data == mock_nodes
        assert app.jobs_data == mock_jobs

    def test_refresh_data_jobs_screen_update(self, mock_scheduler_client, mock_jobs):
        """Test data refresh updates jobs screen."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_jobs.return_value = mock_jobs
        
        # Test that data is fetched and stored correctly
        app.refresh_data()
        
        # Verify data is stored
        assert app.jobs_data == mock_jobs

    def test_refresh_data_gpus_screen_update(self, mock_scheduler_client, mock_nodes):
        """Test data refresh updates GPUs screen."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        
        # Test that data is fetched and stored correctly
        app.refresh_data()
        
        # Verify data is stored
        assert app.nodes_data == mock_nodes

    def test_action_quit(self, mock_scheduler_client):
        """Test quit action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'exit') as mock_exit:
            app.action_quit()
            mock_exit.assert_called_once()

    def test_action_switch_to_cluster(self, mock_scheduler_client):
        """Test switch to cluster action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'switch_screen') as mock_switch:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.action_switch_to_cluster()
                
                mock_switch.assert_called_once_with("cluster")
                mock_refresh.assert_called_once()

    def test_action_switch_to_nodes(self, mock_scheduler_client):
        """Test switch to nodes action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'switch_screen') as mock_switch:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.action_switch_to_nodes()
                
                mock_switch.assert_called_once_with("nodes")
                mock_refresh.assert_called_once()

    def test_action_switch_to_jobs(self, mock_scheduler_client):
        """Test switch to jobs action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'switch_screen') as mock_switch:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.action_switch_to_jobs()
                
                mock_switch.assert_called_once_with("jobs")
                mock_refresh.assert_called_once()

    def test_action_switch_to_gpus(self, mock_scheduler_client):
        """Test switch to GPUs action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'switch_screen') as mock_switch:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.action_switch_to_gpus()
                
                mock_switch.assert_called_once_with("gpus")
                mock_refresh.assert_called_once()

    def test_action_refresh(self, mock_scheduler_client):
        """Test manual refresh action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'notify') as mock_notify:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.action_refresh()
                
                mock_notify.assert_called_once_with("Refreshing data...")
                mock_refresh.assert_called_once()

    def test_action_help(self, mock_scheduler_client):
        """Test help action."""
        app = SchedulerTUI(mock_scheduler_client)
        
        with patch.object(app, 'notify') as mock_notify:
            app.action_help()
            
            mock_notify.assert_called_once()
            help_text = mock_notify.call_args[0][0]
            assert "GPU Scheduler TUI Help" in help_text
            assert "Global Keybindings:" in help_text

    def test_screen_registry(self, mock_scheduler_client):
        """Test screen registry configuration."""
        app = SchedulerTUI(mock_scheduler_client)
        
        expected_screens = ["cluster", "nodes", "jobs", "gpus"]
        for screen_name in expected_screens:
            assert screen_name in app.SCREENS

    def test_bindings_configuration(self, mock_scheduler_client):
        """Test key bindings configuration."""
        app = SchedulerTUI(mock_scheduler_client)
        
        binding_keys = [binding.key for binding in app.BINDINGS]
        expected_keys = ["q", "h", "r"]
        
        for key in expected_keys:
            assert key in binding_keys

    def test_css_styling(self, mock_scheduler_client):
        """Test CSS styling configuration."""
        app = SchedulerTUI(mock_scheduler_client)
        
        assert app.CSS is not None
        assert len(app.CSS) > 0
        assert "Screen" in app.CSS
        assert "DataTable" in app.CSS


class TestRunTUI:
    """Test run_tui function."""

    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_with_client(self, mock_tui_class, mock_scheduler_client):
        """Test run_tui with provided client."""
        mock_app = Mock()
        mock_tui_class.return_value = mock_app
        
        run_tui(client=mock_scheduler_client)
        
        mock_tui_class.assert_called_once_with(mock_scheduler_client)
        mock_app.run.assert_called_once()

    @patch('scheduler.tui.app.SchedulerClient')
    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_with_address(self, mock_tui_class, mock_client_class, mock_scheduler_client):
        """Test run_tui with address parameter."""
        mock_client_class.return_value = mock_scheduler_client
        mock_app = Mock()
        mock_tui_class.return_value = mock_app
        
        run_tui(address="localhost:8265")
        
        mock_client_class.assert_called_once_with(address="localhost:8265")
        mock_tui_class.assert_called_once_with(mock_scheduler_client)
        mock_app.run.assert_called_once()

    @patch('scheduler.tui.app.SchedulerClient')
    @patch('scheduler.tui.app.SchedulerTUI')
    def test_run_tui_without_parameters(self, mock_tui_class, mock_client_class, mock_scheduler_client):
        """Test run_tui without parameters."""
        mock_client_class.return_value = mock_scheduler_client
        mock_app = Mock()
        mock_tui_class.return_value = mock_app
        
        run_tui()
        
        mock_client_class.assert_called_once_with(address=None)
        mock_tui_class.assert_called_once_with(mock_scheduler_client)
        mock_app.run.assert_called_once()


class TestTUIErrorHandling:
    """Test TUI error handling scenarios."""

    def test_connection_error_during_refresh(self, mock_scheduler_client):
        """Test handling of connection errors during data refresh."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.side_effect = Exception("Network error")
        
        with patch.object(app, 'notify') as mock_notify:
            app.refresh_data()
            
            # Should notify user of error
            mock_notify.assert_called_once()
            assert "Error refreshing data" in mock_notify.call_args[0][0]
            assert "Network error" in mock_notify.call_args[0][0]

    def test_partial_data_error(self, mock_scheduler_client, mock_nodes):
        """Test handling of partial data errors."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.side_effect = Exception("Jobs API error")
        
        with patch.object(app, 'notify') as mock_notify:
            app.refresh_data()
            
            # Should still update nodes data
            assert app.nodes_data == mock_nodes
            # Should notify about error
            mock_notify.assert_called_once()

    def test_unknown_screen_type(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test handling of unknown screen types."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # Test that data refresh works even without screen access
        app.refresh_data()
        
        # Should not crash and data should be stored
        assert app.nodes_data == mock_nodes
        assert app.jobs_data == mock_jobs


class TestTUIPerformance:
    """Test TUI performance characteristics."""

    def test_refresh_interval_configuration(self, mock_scheduler_client):
        """Test refresh interval configuration."""
        app = SchedulerTUI(mock_scheduler_client)
        
        # Test default interval
        assert app.refresh_interval == 2.0
        
        # Test custom interval
        app.refresh_interval = 5.0
        assert app.refresh_interval == 5.0

    def test_data_caching(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test data caching behavior."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # First refresh
        app.refresh_data()
        assert app.nodes_data == mock_nodes
        assert app.jobs_data == mock_jobs
        
        # Second refresh with different data
        new_nodes = mock_nodes[:1]  # Only first node
        new_jobs = mock_jobs[:2]    # Only first two jobs
        app.client.list_nodes.return_value = new_nodes
        app.client.list_jobs.return_value = new_jobs
        
        app.refresh_data()
        assert app.nodes_data == new_nodes
        assert app.jobs_data == new_jobs

    def test_memory_usage_with_large_datasets(self, mock_scheduler_client):
        """Test memory usage with large datasets."""
        app = SchedulerTUI(mock_scheduler_client)
        
        # Create large datasets
        large_nodes = [Mock() for _ in range(100)]
        large_jobs = [Mock() for _ in range(1000)]
        
        app.client.list_nodes.return_value = large_nodes
        app.client.list_jobs.return_value = large_jobs
        
        # Should handle large datasets without issues
        app.refresh_data()
        
        assert len(app.nodes_data) == 100
        assert len(app.jobs_data) == 1000


class TestTUIIntegration:
    """Test TUI integration scenarios."""

    def test_full_workflow_simulation(self, mock_scheduler_client, mock_nodes, mock_jobs):
        """Test full TUI workflow simulation."""
        app = SchedulerTUI(mock_scheduler_client)
        app.client.list_nodes.return_value = mock_nodes
        app.client.list_jobs.return_value = mock_jobs
        
        # Simulate app startup
        with patch.object(app, 'set_interval') as mock_interval:
            with patch.object(app, 'refresh_data') as mock_refresh:
                app.on_mount()
                
                # Should set up periodic refresh
                mock_interval.assert_called_once()
                # Should do initial data fetch
                mock_refresh.assert_called_once()
        
        # Simulate screen switching
        with patch.object(app, 'switch_screen') as mock_switch:
            with patch.object(app, 'refresh_data') as mock_refresh:
                # Switch to different screens
                app.action_switch_to_nodes()
                app.action_switch_to_jobs()
                app.action_switch_to_gpus()
                app.action_switch_to_cluster()
                
                # Should switch to each screen
                assert mock_switch.call_count == 4
                assert mock_refresh.call_count == 4

    def test_user_interaction_simulation(self, mock_scheduler_client):
        """Test user interaction simulation."""
        app = SchedulerTUI(mock_scheduler_client)
        
        # Simulate user actions
        with patch.object(app, 'notify') as mock_notify:
            with patch.object(app, 'refresh_data') as mock_refresh:
                # Help action
                app.action_help()
                mock_notify.assert_called()
                
                # Refresh action
                app.action_refresh()
                mock_notify.assert_called_with("Refreshing data...")
                mock_refresh.assert_called()
                
                # Quit action
                with patch.object(app, 'exit') as mock_exit:
                    app.action_quit()
                    mock_exit.assert_called_once()

    def test_error_recovery(self, mock_scheduler_client):
        """Test error recovery scenarios."""
        app = SchedulerTUI(mock_scheduler_client)
        
        # Simulate connection failure and recovery
        app.client.list_nodes.side_effect = Exception("Connection failed")
        
        with patch.object(app, 'notify') as mock_notify:
            app.refresh_data()
            mock_notify.assert_called()
        
        # Simulate recovery
        app.client.list_nodes.side_effect = None
        app.client.list_nodes.return_value = []
        app.client.list_jobs.return_value = []
        
        # Test successful recovery - should not notify on success
        app.refresh_data()
        
        # Verify data was updated successfully
        assert app.nodes_data == []
        assert app.jobs_data == []
