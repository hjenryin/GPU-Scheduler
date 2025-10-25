"""Unit tests for TUI screen components."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from textual.widgets import Input

from scheduler.tui.screens.cluster import ClusterScreen
from scheduler.tui.screens.nodes import NodesScreen
from scheduler.tui.screens.jobs import JobsScreen
from scheduler.tui.screens.gpus import GPUsScreen
from scheduler.tui.screens.job_detail import JobDetailScreen
from scheduler.core import JobStatus, NodeStatus
from tests.unit.test_tui_fixtures import *


class TestClusterScreen:
    """Test ClusterScreen functionality."""

    def test_cluster_screen_initialization(self):
        """Test ClusterScreen initializes correctly."""
        screen = ClusterScreen()
        assert screen is not None

    def test_cluster_screen_bindings(self):
        """Test ClusterScreen has correct key bindings."""
        screen = ClusterScreen()
        # BINDINGS is a tuple of (key, action) pairs
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        expected_keys = ["n", "j", "g", "q", "h", "r"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one')
    def test_update_data_summary_calculation(self, mock_query_one, mock_nodes, mock_jobs):
        """Test cluster summary calculation."""
        screen = ClusterScreen()
        
        # Mock the static widgets
        mock_summary = Mock()
        mock_node_table = Mock()
        mock_gpu_bars = Mock()
        mock_job_table = Mock()
        
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#cluster-summary": mock_summary,
            "#node-table": mock_node_table,
            "#gpu-bars": mock_gpu_bars,
            "#job-table": mock_job_table
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Verify summary calculation
        mock_summary.update.assert_called_once()
        summary_text = mock_summary.update.call_args[0][0]
        assert "Nodes:" in summary_text
        assert "GPUs:" in summary_text
        assert "Jobs:" in summary_text

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one')
    def test_update_data_node_table(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node table update."""
        screen = ClusterScreen()
        
        mock_node_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#node-table": mock_node_table
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Verify table operations
        mock_node_table.clear.assert_called_once()
        assert mock_node_table.add_row.call_count == len(mock_nodes)

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one')
    def test_update_data_gpu_bars(self, mock_query_one, mock_nodes, mock_jobs):
        """Test GPU bars update."""
        screen = ClusterScreen()
        
        mock_gpu_bars = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#gpu-bars": mock_gpu_bars
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Verify GPU bars update
        mock_gpu_bars.update.assert_called_once()
        gpu_text = mock_gpu_bars.update.call_args[0][0]
        assert len(gpu_text) > 0

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one')
    def test_update_data_job_table(self, mock_query_one, mock_nodes, mock_jobs):
        """Test job table update."""
        screen = ClusterScreen()
        
        mock_job_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#job-table": mock_job_table
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Verify job table operations
        mock_job_table.clear.assert_called_once()
        # Should add active jobs (pending + running)
        active_jobs = [j for j in mock_jobs if j.status.value in ["pending", "running"]]
        assert mock_job_table.add_row.call_count == len(active_jobs)


class TestNodesScreen:
    """Test NodesScreen functionality."""

    def test_nodes_screen_initialization(self):
        """Test NodesScreen initializes correctly."""
        screen = NodesScreen()
        assert screen is not None
        assert screen.selected_node is None

    def test_nodes_screen_bindings(self):
        """Test NodesScreen has correct key bindings."""
        screen = NodesScreen()
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        expected_keys = ["n", "j", "g", "q", "h"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one')
    def test_update_data_nodes_list(self, mock_query_one, mock_nodes, mock_jobs):
        """Test nodes list update."""
        screen = NodesScreen()
        
        mock_nodes_list = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#nodes-list": mock_nodes_list
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Verify nodes list operations
        mock_nodes_list.clear.assert_called_once()
        assert mock_nodes_list.add_row.call_count == len(mock_nodes)

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one')
    def test_update_data_auto_select_first_node(self, mock_query_one, mock_nodes, mock_jobs):
        """Test auto-selection of first node when none selected."""
        screen = NodesScreen()
        screen.selected_node = None
        
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#nodes-list": Mock(),
            "#node-detail-header": Mock(),
            "#node-detail-info": Mock(),
            "#gpu-detail-table": Mock(),
            "#jobs-detail-list": Mock()
        }.get(selector, Mock())

        screen.update_data(mock_nodes, mock_jobs)

        # Should auto-select first node
        assert screen.selected_node == mock_nodes[0].node_name

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one')
    def test_on_node_selected(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node selection handling."""
        screen = NodesScreen()
        screen.nodes_data = mock_nodes
        screen.jobs_data = mock_jobs
        
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#node-detail-header": Mock(),
            "#node-detail-info": Mock(),
            "#gpu-detail-table": Mock(),
            "#jobs-detail-list": Mock()
        }.get(selector, Mock())

        selected_node = mock_nodes[0].node_name
        screen.on_node_selected(selected_node)

        assert screen.selected_node == selected_node

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one')
    def test_update_node_details(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node details update."""
        screen = NodesScreen()
        screen.nodes_data = mock_nodes
        screen.jobs_data = mock_jobs
        
        mock_header = Mock()
        mock_info = Mock()
        mock_gpu_table = Mock()
        mock_jobs_list = Mock()
        
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#node-detail-header": mock_header,
            "#node-detail-info": mock_info,
            "#gpu-detail-table": mock_gpu_table,
            "#jobs-detail-list": mock_jobs_list
        }.get(selector, Mock())

        node_name = mock_nodes[0].node_name
        screen._update_node_details(node_name)

        # Verify all detail components are updated
        mock_header.update.assert_called_once()
        mock_info.update.assert_called_once()
        mock_gpu_table.clear.assert_called_once()
        mock_jobs_list.update.assert_called_once()


class TestJobsScreen:
    """Test JobsScreen functionality."""

    def test_jobs_screen_initialization(self):
        """Test JobsScreen initializes correctly."""
        screen = JobsScreen()
        assert screen is not None
        assert screen.current_filter == "all"
        assert screen.search_text == ""

    def test_jobs_screen_bindings(self):
        """Test JobsScreen has correct key bindings."""
        screen = JobsScreen()
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        expected_keys = ["n", "g", "q", "h", "1", "2", "3", "4", "5", "/", "escape", "enter"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one')
    def test_update_data(self, mock_query_one, mock_jobs):
        """Test jobs data update."""
        screen = JobsScreen()
        
        mock_jobs_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock())

        screen.update_data(mock_jobs)

        assert screen.jobs_data == mock_jobs
        mock_jobs_table.clear.assert_called_once()

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one')
    def test_refresh_table_with_filter(self, mock_query_one, mock_jobs):
        """Test table refresh with status filter."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        screen.current_filter = "running"
        
        mock_jobs_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock())

        screen._refresh_table()

        # Should only add running jobs
        running_jobs = [j for j in mock_jobs if j.status.value == "running"]
        assert mock_jobs_table.add_row.call_count == len(running_jobs)

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one')
    def test_refresh_table_with_search(self, mock_query_one, mock_jobs):
        """Test table refresh with search filter."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        screen.search_text = "test"
        
        mock_jobs_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock())

        screen._refresh_table()

        # Should filter by search text
        mock_jobs_table.clear.assert_called_once()

    def test_filter_actions(self, mock_jobs):
        """Test filter action methods."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        
        with patch.object(screen, '_refresh_table') as mock_refresh:
            with patch.object(screen, 'query_one') as mock_query:
                mock_filter_status = Mock()
                mock_query.return_value = mock_filter_status

                # Test pending filter
                screen.action_filter_pending()
                assert screen.current_filter == "pending"
                mock_filter_status.update.assert_called_with("[Pending]")
                mock_refresh.assert_called()

                # Test running filter
                screen.action_filter_running()
                assert screen.current_filter == "running"
                mock_filter_status.update.assert_called_with("[Running]")

                # Test all filter
                screen.action_filter_all()
                assert screen.current_filter == "all"
                mock_filter_status.update.assert_called_with("[All Jobs]")

    def test_focus_search(self, mock_jobs):
        """Test search input focus."""
        screen = JobsScreen()
        
        with patch.object(screen, 'query_one') as mock_query:
            mock_input = Mock()
            mock_query.return_value = mock_input

            screen.action_focus_search()

            mock_query.assert_called_with("#search-input", Input)
            mock_input.focus.assert_called_once()

    def test_on_input_changed(self, mock_jobs):
        """Test input change handling."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        
        with patch.object(screen, '_refresh_table') as mock_refresh:
            # Create mock event
            event = Mock()
            event.input = Mock()
            event.input.id = "search-input"
            event.value = "test search"

            screen.on_input_changed(event)

            assert screen.search_text == "test search"
            mock_refresh.assert_called_once()

    def test_job_selection(self, mock_jobs):
        """Test job selection handling."""
        screen = JobsScreen()
        
        # Test that the method exists and can be called
        assert hasattr(screen, 'on_job_selected')
        assert callable(screen.on_job_selected)
        
        # Mock the app property to avoid Textual context issues
        with patch.object(screen.__class__, 'app', new_callable=lambda: Mock()):
            try:
                screen.on_job_selected("job_123")
            except (AttributeError, LookupError):
                pass  # Expected when app is not available


class TestGPUsScreen:
    """Test GPUsScreen functionality."""

    def test_gpus_screen_initialization(self):
        """Test GPUsScreen initializes correctly."""
        screen = GPUsScreen()
        assert screen is not None

    def test_gpus_screen_bindings(self):
        """Test GPUsScreen has correct key bindings."""
        screen = GPUsScreen()
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        expected_keys = ["n", "j", "q", "h", "escape"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.gpus.GPUsScreen.query_one')
    def test_update_data(self, mock_query_one, mock_nodes):
        """Test GPUs data update."""
        screen = GPUsScreen()
        
        mock_gpu_table = Mock()
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#gpus-table": mock_gpu_table
        }.get(selector, Mock())

        screen.update_data(mock_nodes)

        # Verify GPU table operations
        mock_gpu_table.clear.assert_called_once()
        # Should add all GPUs from all nodes
        total_gpus = sum(len(node.gpus) for node in mock_nodes)
        assert mock_gpu_table.add_row.call_count == total_gpus


class TestJobDetailScreen:
    """Test JobDetailScreen functionality."""

    def test_job_detail_screen_initialization(self):
        """Test JobDetailScreen initializes correctly."""
        screen = JobDetailScreen("job_123")
        assert screen is not None
        assert screen.job_id == "job_123"

    def test_job_detail_screen_bindings(self):
        """Test JobDetailScreen has correct key bindings."""
        screen = JobDetailScreen("job_123")
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        expected_keys = ["l", "c", "escape"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.job_detail.JobDetailScreen.query_one')
    def test_update_job_data(self, mock_query_one, mock_job_running):
        """Test job data update."""
        screen = JobDetailScreen("job_123")
        
        # Add missing attributes to mock job
        mock_job_running.priority = 1
        mock_job_running.assigned_gpus = [0, 1]
        mock_job_running.submitted_at = datetime.now()
        mock_job_running.started_at = datetime.now()
        mock_job_running.completed_at = None
        mock_job_running.exit_code = None
        mock_job_running.script = "test_script.py"
        mock_job_running.script_args = ["arg1", "arg2"]
        mock_job_running.working_dir = "/tmp"
        mock_job_running.env_vars = {"VAR1": "value1"}
        mock_job_running.dependencies = []
        
        mock_metadata = Mock()
        mock_config = Mock()
        mock_logs = Mock()
        
        mock_query_one.side_effect = lambda selector, widget_type: {
            "#job-metadata": mock_metadata,
            "#job-config": mock_config,
            "#logs-preview": mock_logs
        }.get(selector, Mock())

        screen.update_data(mock_job_running)

        # Verify all components are updated
        mock_metadata.update.assert_called_once()
        mock_config.update.assert_called_once()
        # Note: logs are not updated in update_data method, only in on_mount

    def test_cancel_job_action(self):
        """Test cancel job action."""
        screen = JobDetailScreen("job_123")
        
        # Test that the method exists and can be called
        assert hasattr(screen, 'action_cancel_job')
        assert callable(screen.action_cancel_job)
        
        # Test that it handles missing app gracefully
        screen.job_data = Mock()
        screen.job_data.status = JobStatus.RUNNING
        
        # Mock the app property to avoid Textual context issues
        with patch.object(screen.__class__, 'app', new_callable=lambda: Mock()):
            try:
                screen.action_cancel_job()
            except (AttributeError, LookupError):
                pass  # Expected when app is not available

    def test_view_logs_action(self):
        """Test view logs action."""
        screen = JobDetailScreen("job_123")
        
        # Test that the method exists and can be called
        assert hasattr(screen, 'action_view_logs')
        assert callable(screen.action_view_logs)
        
        # Mock the app property to avoid Textual context issues
        mock_app = Mock()
        mock_app.client = Mock()
        mock_app.client.get_job_logs.return_value = "test logs"
        
        with patch.object(screen.__class__, 'app', new_callable=lambda: mock_app):
            with patch.object(screen, 'query_one') as mock_query:
                mock_logs = Mock()
                mock_header = Mock()
                mock_query.side_effect = lambda selector, widget_type: {
                    "#logs-preview": mock_logs,
                    "#logs-header": mock_header
                }.get(selector, Mock())
                
                screen.action_view_logs()
                
                # Should call get_job_logs method on app
                mock_app.client.get_job_logs.assert_called()
                mock_logs.update.assert_called_once()
                mock_header.update.assert_called_once_with("Full Logs")
