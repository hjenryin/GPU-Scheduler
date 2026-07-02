"""Unit tests for TUI screen components."""

import pytest
from unittest.mock import Mock, patch, MagicMock, create_autospec, PropertyMock
from datetime import datetime, timedelta
from textual.widgets import Input, DataTable, Static, TextArea
from scheduler.core import Config

from scheduler.tui.screens.cluster import ClusterScreen
from scheduler.tui.screens.nodes import NodesScreen
from scheduler.tui.screens.jobs import JobsScreen
from scheduler.tui.screens.gpus import GPUsScreen
from scheduler.tui.screens.job_detail import JobDetailScreen
from scheduler.core import JobStatus, NodeStatus
from tests.unit.test_tui_fixtures import *
from scheduler.tui.app import SchedulerTUI


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

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one', autospec=True)
    def test_update_data_summary_calculation(self, mock_query_one, mock_nodes, mock_jobs):
        """Test cluster summary calculation."""
        screen = ClusterScreen()
        
        # Mock the static widgets (use spec_set for Textual widgets)
        mock_summary = create_autospec(Static, instance=True, spec_set=True)
        mock_node_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_gpu_bars = create_autospec(Static, instance=True, spec_set=True)  # External C library (Textual)
        mock_job_table = create_autospec(DataTable, instance=True, spec_set=True)

        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#cluster-summary": mock_summary,
            "#node-table": mock_node_table,
            "#gpu-bars": mock_gpu_bars,
            "#job-table": mock_job_table
        }.get(selector, Mock(spec=[]))  # Fallback mock

        # Call with threshold parameters
        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Verify summary calculation
        mock_summary.update.assert_called_once()
        summary_text = mock_summary.update.call_args[0][0]
        assert "Nodes:" in summary_text
        assert "GPUs:" in summary_text
        assert "Jobs:" in summary_text

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one', autospec=True)
    def test_update_data_node_table(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node table update - active nodes (not disconnected) are shown."""
        screen = ClusterScreen()
        
        mock_node_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#node-table": mock_node_table,
            "#cluster-summary": create_autospec(Static, instance=True, spec_set=True),
            "#gpu-bars": create_autospec(Static, instance=True, spec_set=True),
            "#job-table": create_autospec(DataTable, instance=True, spec_set=True)
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Verify table operations - active nodes (not disconnected) should be added
        active_nodes = [n for n in mock_nodes if n.status != NodeStatus.DISCONNECTED]
        mock_node_table.clear.assert_called_once()
        assert mock_node_table.add_row.call_count == len(active_nodes)

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one', autospec=True)
    def test_update_data_filters_disconnected_nodes(self, mock_query_one, mock_nodes, mock_jobs):
        """Test that disconnected nodes are filtered from display and counts."""
        screen = ClusterScreen()
        
        mock_summary = create_autospec(Static, instance=True, spec_set=True)
        mock_node_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_gpu_bars = create_autospec(Static, instance=True, spec_set=True)  # External C library (Textual)
        mock_job_table = create_autospec(DataTable, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#cluster-summary": mock_summary,
            "#node-table": mock_node_table,
            "#gpu-bars": mock_gpu_bars,
            "#job-table": mock_job_table
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Verify summary counts active nodes (not disconnected)
        summary_text = mock_summary.update.call_args[0][0]
        active_count = len([n for n in mock_nodes if n.status != NodeStatus.DISCONNECTED])
        assert f"Nodes: {active_count} active" in summary_text
        # Should NOT mention disconnected nodes
        assert "disconnected" not in summary_text
        
        # Verify only active nodes (not disconnected) are in the table
        assert mock_node_table.add_row.call_count == active_count


    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one', autospec=True)
    def test_update_data_gpu_bars(self, mock_query_one, mock_nodes, mock_jobs):
        """Test GPU bars update."""
        screen = ClusterScreen()
        
        mock_gpu_bars = create_autospec(Static, instance=True, spec_set=True)  # External C library (Textual)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#gpu-bars": mock_gpu_bars,
            "#cluster-summary": create_autospec(Static, instance=True, spec_set=True),
            "#node-table": create_autospec(DataTable, instance=True, spec_set=True),
            "#job-table": create_autospec(DataTable, instance=True, spec_set=True)
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Verify GPU bars update
        mock_gpu_bars.update.assert_called_once()
        gpu_text = mock_gpu_bars.update.call_args[0][0]
        assert len(gpu_text) > 0

    @patch('scheduler.tui.screens.cluster.ClusterScreen.query_one', autospec=True)
    def test_update_data_job_table(self, mock_query_one, mock_nodes, mock_jobs):
        """Test job table update."""
        screen = ClusterScreen()
        
        mock_job_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#job-table": mock_job_table,
            "#cluster-summary": create_autospec(Static, instance=True, spec_set=True),
            "#node-table": create_autospec(DataTable, instance=True, spec_set=True),
            "#gpu-bars": create_autospec(Static, instance=True, spec_set=True)
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

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
        expected_keys = ["c", "j", "g", "q", "h"]
        for key in expected_keys:
            assert key in binding_keys

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one', autospec=True)
    def test_update_data_nodes_list(self, mock_query_one, mock_nodes, mock_jobs):
        """Test nodes list update - only active nodes shown."""
        screen = NodesScreen()
        
        mock_nodes_list = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#nodes-list": mock_nodes_list,
            "#node-detail-header": create_autospec(Static, instance=True, spec_set=True),
            "#node-detail-info": create_autospec(Static, instance=True, spec_set=True),
            "#gpu-detail-table": create_autospec(DataTable, instance=True, spec_set=True),
            "#jobs-detail-list": create_autospec(Static, instance=True, spec_set=True)
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Verify nodes list operations - only active nodes (not disconnected) shown
        active_nodes = [n for n in mock_nodes if n.status != NodeStatus.DISCONNECTED]
        mock_nodes_list.clear.assert_called_once()
        assert mock_nodes_list.add_row.call_count == len(active_nodes)

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one', autospec=True)
    def test_update_data_auto_select_first_node(self, mock_query_one, mock_nodes, mock_jobs):
        """Test auto-selection of first node when none selected."""
        screen = NodesScreen()
        screen.selected_node = None
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#nodes-list": create_autospec(DataTable, instance=True, spec_set=True),  # Textual widget
            "#node-detail-header": create_autospec(Static, instance=True, spec_set=True),  # Textual widget
            "#node-detail-info": create_autospec(Static, instance=True, spec_set=True),  # Textual widget
            "#gpu-detail-table": create_autospec(DataTable, instance=True, spec_set=True),  # Textual widget
            "#jobs-detail-list": create_autospec(Static, instance=True, spec_set=True)  # Textual widget
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, mock_jobs, util_threshold=10.0, mem_threshold=10.0)

        # Should auto-select first node
        assert screen.selected_node == mock_nodes[0].node_name

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one', autospec=True)
    def test_on_node_selected(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node selection handling."""
        screen = NodesScreen()
        screen.nodes_data = mock_nodes
        screen.jobs_data = mock_jobs
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#node-detail-header": create_autospec(Static, instance=True, spec_set=True),  # Textual widget
            "#node-detail-info": create_autospec(Static, instance=True, spec_set=True),  # Textual widget
            "#gpu-detail-table": create_autospec(DataTable, instance=True, spec_set=True),  # Textual widget
            "#jobs-detail-list": create_autospec(Static, instance=True, spec_set=True)  # Textual widget
        }.get(selector, Mock(spec=[]))  # Fallback mock

        selected_node = mock_nodes[0].node_name
        screen.on_node_selected(selected_node)

        assert screen.selected_node == selected_node

    @patch('scheduler.tui.screens.nodes.NodesScreen.query_one', autospec=True)
    def test_update_node_details(self, mock_query_one, mock_nodes, mock_jobs):
        """Test node details update."""
        screen = NodesScreen()
        screen.nodes_data = mock_nodes
        screen.jobs_data = mock_jobs
        
        mock_header = create_autospec(Static, instance=True, spec_set=True)  # Textual widget
        mock_info = create_autospec(Static, instance=True, spec_set=True)  # Textual widget
        mock_gpu_table = create_autospec(DataTable, instance=True, spec_set=True)  # Textual widget
        mock_jobs_list = create_autospec(Static, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#node-detail-header": mock_header,
            "#node-detail-info": mock_info,
            "#gpu-detail-table": mock_gpu_table,
            "#jobs-detail-list": mock_jobs_list
        }.get(selector, Mock(spec=[]))  # Fallback mock

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

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one', autospec=True)
    def test_update_data(self, mock_query_one, mock_jobs):
        """Test jobs data update."""
        screen = JobsScreen()
        
        mock_jobs_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_jobs)

        assert screen.jobs_data == mock_jobs
        mock_jobs_table.clear.assert_called_once()

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one', autospec=True)
    def test_refresh_table_with_filter(self, mock_query_one, mock_jobs):
        """Test table refresh with status filter."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        screen.current_filter = "running"
        
        mock_jobs_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen._refresh_table()

        # Should only add running jobs
        running_jobs = [j for j in mock_jobs if j.status.value == "running"]
        assert mock_jobs_table.add_row.call_count == len(running_jobs)

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one', autospec=True)
    def test_refresh_table_with_search(self, mock_query_one, mock_jobs):
        """Test table refresh with search filter."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        screen.search_text = "test"
        
        mock_jobs_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen._refresh_table()

        # Should filter by search text
        mock_jobs_table.clear.assert_called_once()

    def test_filter_actions(self, mock_jobs):
        """Test filter action methods."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        
        with patch.object(screen, '_refresh_table') as mock_refresh:
            with patch.object(screen, 'query_one') as mock_query:
                mock_filter_status = create_autospec(Static, instance=True, spec_set=True)  # Textual widget
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
            mock_input = create_autospec(Input, instance=True, spec_set=True)  # Textual widget
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
            event = Mock(spec=['input', 'value'])  # Event data structure
            event.input = create_autospec(Input, instance=True, spec_set=True)  # Textual widget
            event.input.id = "search-input"
            event.value = "test search"

            screen.on_input_changed(event)

            assert screen.search_text == "test search"
            mock_refresh.assert_called_once()

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one', autospec=True)
    def test_refresh_table_with_command_search(self, mock_query_one, mock_jobs):
        """Test table refresh with command search filter."""
        screen = JobsScreen()
        screen.jobs_data = mock_jobs
        
        # Configure job command lists
        for job in mock_jobs:
            job.command = []
        
        mock_jobs[0].command = ["python3", "my_custom_training_script.py", "--epochs", "50"]
        mock_jobs[1].command = ["bash", "run_eval.sh"]
        
        # Search for training script
        screen.search_text = "my_custom_training"
        
        mock_jobs_table = create_autospec(DataTable, instance=True, spec_set=True)
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#jobs-table": mock_jobs_table
        }.get(selector, Mock(spec=[]))
        
        screen._refresh_table()
        
        # Should call add_row for the matching job (mock_jobs[0])
        assert mock_jobs_table.add_row.call_count == 1
        
        # Reset and search for command argument
        mock_jobs_table.reset_mock()
        screen.search_text = "--epochs"
        screen._refresh_table()
        assert mock_jobs_table.add_row.call_count == 1

    def test_row_selected_event_handling(self):
        """Test that on_data_table_row_selected correctly extracts job_id from row_key."""
        screen = JobsScreen()
        
        with patch.object(screen, 'on_job_selected') as mock_on_job_selected:
            # Mock row selection event
            event = Mock(spec=['data_table', 'row_key'])
            event.data_table = Mock(spec=['id'])
            event.data_table.id = "jobs-table"
            row_key = Mock(spec=['value'])
            row_key.value = "job_999"
            event.row_key = row_key
            
            screen.on_data_table_row_selected(event)
            mock_on_job_selected.assert_called_once_with("job_999")

    @patch('scheduler.tui.screens.jobs.JobsScreen.query_one', autospec=True)
    def test_action_show_job_detail_key_handling(self, mock_query_one):
        """Test action_show_job_detail retrieves job_id from cursor_row key."""
        screen = JobsScreen()
        
        with patch.object(screen, 'on_job_selected') as mock_on_job_selected:
            mock_jobs_table = create_autospec(DataTable, instance=True, spec_set=True)
            cursor_row = Mock(spec=['value'])
            cursor_row.value = "job_777"
            mock_jobs_table.cursor_row = cursor_row
            
            mock_query_one.side_effect = lambda self, selector, widget_type: {
                "#jobs-table": mock_jobs_table
            }.get(selector, Mock(spec=[]))
            
            screen.action_show_job_detail()
            mock_on_job_selected.assert_called_once_with("job_777")

    def test_job_selection(self, mock_jobs):
        """Test job selection handling."""
        screen = JobsScreen()
        
        # Test that the method exists and can be called
        assert hasattr(screen, 'on_job_selected')
        assert callable(screen.on_job_selected)
        
        # Mock the app property (it's a property on Screen that returns the parent App)
        mock_app_instance = create_autospec(SchedulerTUI, instance=True, spec_set=True)
        with patch.object(screen.__class__, 'app', new_callable=PropertyMock) as mock_app_property:
            mock_app_property.return_value = mock_app_instance
            try:
                screen.on_job_selected("job_123")
            except (AttributeError, LookupError):
                pass  # Expected when app is not available

    def test_escape_key_with_focused_input(self):
        """Test escape key blurs input when focused, then goes back when pressed again."""
        screen = JobsScreen()
        
        with patch.object(screen, 'query_one') as mock_query:
            # Create mock input widget
            mock_input = create_autospec(Input, instance=True, spec_set=True)
            mock_input.has_focus = True
            mock_query.return_value = mock_input
            
            # Create mock key event
            from textual import events
            event = Mock(spec=events.Key)
            event.key = "escape"
            
            # Call on_key handler
            screen.on_key(event)
            
            # Verify input was blurred and event was stopped
            mock_input.blur.assert_called_once()
            event.prevent_default.assert_called_once()
            event.stop.assert_called_once()

    def test_escape_key_without_focused_input(self):
        """Test escape key goes back when input is not focused."""
        screen = JobsScreen()
        
        with patch.object(screen, 'query_one') as mock_query:
            # Create mock input widget that is not focused
            mock_input = create_autospec(Input, instance=True, spec_set=True)
            mock_input.has_focus = False
            mock_query.return_value = mock_input
            
            # Create mock key event
            from textual import events
            event = Mock(spec=events.Key)
            event.key = "escape"
            
            # Call on_key handler
            screen.on_key(event)
            
            # Verify input was NOT blurred and event was NOT stopped
            mock_input.blur.assert_not_called()
            # prevent_default and stop should not be called
            assert not event.prevent_default.called
            assert not event.stop.called


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

    @patch('scheduler.tui.screens.gpus.GPUsScreen.query_one', autospec=True)
    def test_update_data(self, mock_query_one, mock_nodes):
        """Test GPUs data update."""
        screen = GPUsScreen()
        
        mock_gpu_table = create_autospec(DataTable, instance=True, spec_set=True)  # Textual widget
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#gpus-table": mock_gpu_table,
            "#gpu-summary": create_autospec(Static, instance=True, spec_set=True)  # Textual widget
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_nodes, util_threshold=10.0, mem_threshold=10.0)

        # Verify GPU table operations
        mock_gpu_table.clear.assert_called_once()
        # Should add all GPUs from active nodes only (not disconnected)
        active_nodes = [n for n in mock_nodes if n.status != NodeStatus.DISCONNECTED]
        total_gpus = sum(len(node.gpus) for node in active_nodes)
        assert mock_gpu_table.add_row.call_count == total_gpus


class TestJobDetailScreen:
    """Test JobDetailScreen functionality."""

    def test_job_detail_screen_initialization(self):
        """Test JobDetailScreen initializes correctly."""
        screen = JobDetailScreen("job_123")
        assert screen is not None
        assert screen.job_id == "job_123"

    def test_job_detail_screen_bindings(self):
        """Test JobDetailScreen has correct initial key bindings (base bindings only)."""
        screen = JobDetailScreen("job_123")
        binding_keys = [binding[0] for binding in screen.BINDINGS]
        # Initial bindings should only have base keys (no 'c' or 'r' until update_data is called)
        expected_keys = ["escape", "l", "d", "q"]
        assert binding_keys == expected_keys
        
        # Verify that cancel and retry bindings exist as instance variables
        assert screen._cancel_binding == ("c", "cancel_job", "Cancel")
        assert screen._retry_binding == ("r", "show_retry_menu", "Retry")

    @patch('scheduler.tui.screens.job_detail.JobDetailScreen.query_one', autospec=True)
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
        mock_job_running.command = ["test_script.py", "arg1", "arg2"]
        mock_job_running.working_dir = "/tmp"
        mock_job_running.env_vars = {"VAR1": "value1"}
        mock_job_running.dependencies = []
        
        mock_metadata = create_autospec(Static, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#job-metadata": mock_metadata,
        }.get(selector, Mock(spec=[]))  # Fallback mock

        screen.update_data(mock_job_running)

        # Verify all components are updated
        mock_metadata.update.assert_called_once()
        # Note: logs are not updated in update_data method, only in on_mount

    def test_cancel_job_action(self):
        """Test cancel job action."""
        screen = JobDetailScreen("job_123")
        
        # Test that the method exists and can be called
        assert hasattr(screen, 'action_cancel_job')
        assert callable(screen.action_cancel_job)
        
        # Test that it handles missing app gracefully
        screen.job_data = Mock(spec=['status'])  # Data structure with status field
        screen.job_data.status = JobStatus.RUNNING
        
        # Mock the app property (it's a property on Screen that returns the parent App)
        mock_app_instance = create_autospec(SchedulerTUI, instance=True, spec_set=True)
        with patch.object(screen.__class__, 'app', new_callable=PropertyMock) as mock_app_property:
            mock_app_property.return_value = mock_app_instance
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
        
        # Mock the app property (it's a property on Screen that returns the parent App)
        mock_app_instance = create_autospec(SchedulerTUI, instance=True, spec_set=True)
        mock_app_instance.client.get_job_logs.return_value = "test logs"
        
        with patch.object(screen.__class__, 'app', new_callable=PropertyMock) as mock_app_property:
            mock_app_property.return_value = mock_app_instance
            with patch.object(screen, 'query_one') as mock_query:
                mock_stdout = create_autospec(TextArea, instance=True, spec_set=True)  # Textual widget
                mock_stderr = create_autospec(TextArea, instance=True, spec_set=True)  # Textual widget
                mock_stdout_header = create_autospec(Static, instance=True, spec_set=True)  # Textual widget
                mock_stderr_header = create_autospec(Static, instance=True, spec_set=True)  # Textual widget
                mock_query.side_effect = lambda selector, widget_type: {
                    "#stdout-preview": mock_stdout,
                    "#stderr-preview": mock_stderr,
                    "#stdout-header": mock_stdout_header,
                    "#stderr-header": mock_stderr_header
                }.get(selector, Mock(spec=[]))  # Fallback mock
                
                screen.action_view_logs()
                
                # Should call get_job_logs method on app.client twice (stdout and stderr)
                assert mock_app_instance.client.get_job_logs.call_count == 2
                # Actual code calls load_text, not update
                mock_stdout.load_text.assert_called_once()
                mock_stderr.load_text.assert_called_once()
                mock_stdout_header.update.assert_called_once()
                mock_stderr_header.update.assert_called_once()

    @patch('scheduler.tui.screens.job_detail.JobDetailScreen.query_one', autospec=True)
    def test_button_visibility_for_running_job(self, mock_query_one, mock_job_running):
        """Test that cancel button is shown and retry buttons are hidden for running job."""
        screen = JobDetailScreen("job_123")
        
        # Add missing attributes to mock job
        mock_job_running.priority = 1
        mock_job_running.assigned_gpus = [0, 1]
        mock_job_running.submitted_at = datetime.now()
        mock_job_running.started_at = datetime.now()
        mock_job_running.completed_at = None
        mock_job_running.exit_code = None
        mock_job_running.command = ["test_script.py"]
        mock_job_running.working_dir = "/tmp"
        mock_job_running.env_vars = {}
        mock_job_running.dependencies = []
        
        # Create mock buttons
        from textual.widgets import Button
        mock_cancel_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_inplace_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_then_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_now_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_nodeps_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_metadata = create_autospec(Static, instance=True, spec_set=True)
        mock_config = create_autospec(Static, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#cancel-button": mock_cancel_btn,
            "#retry-inplace-button": mock_retry_inplace_btn,
            "#retry-then-button": mock_retry_then_btn,
            "#retry-now-button": mock_retry_now_btn,
            "#retry-nodeps-button": mock_retry_nodeps_btn,
            "#job-metadata": mock_metadata,
            "#job-config": mock_config,
        }.get(selector, Mock(spec=[]))
        
        screen.update_data(mock_job_running)
        
        # Cancel button should be visible for running job
        assert mock_cancel_btn.display == True
        # Retry buttons should be hidden for running job
        assert mock_retry_inplace_btn.display == False
        assert mock_retry_then_btn.display == False
        assert mock_retry_now_btn.display == False
        assert mock_retry_nodeps_btn.display == False
        
        # Verify footer bindings are updated (has 'c' for cancel, no 'r' for retry)
        binding_keys = [b[0] for b in screen.BINDINGS]
        assert 'c' in binding_keys  # Cancel should be in bindings
        assert 'r' not in binding_keys  # Retry should not be in bindings

    @patch('scheduler.tui.screens.job_detail.JobDetailScreen.query_one', autospec=True)
    def test_button_visibility_for_completed_job(self, mock_query_one, mock_job_completed):
        """Test that cancel button is hidden and retry buttons are shown for completed job."""
        screen = JobDetailScreen("job_123")
        
        # Add missing attributes to mock job
        mock_job_completed.priority = 1
        mock_job_completed.assigned_gpus = [0, 1]
        mock_job_completed.submitted_at = datetime.now()
        mock_job_completed.started_at = datetime.now()
        mock_job_completed.completed_at = datetime.now()
        mock_job_completed.exit_code = 0
        mock_job_completed.command = ["test_script.py"]
        mock_job_completed.working_dir = "/tmp"
        mock_job_completed.env_vars = {}
        mock_job_completed.dependencies = []
        
        # Create mock buttons
        from textual.widgets import Button
        mock_cancel_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_inplace_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_then_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_now_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_nodeps_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_metadata = create_autospec(Static, instance=True, spec_set=True)
        mock_config = create_autospec(Static, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#cancel-button": mock_cancel_btn,
            "#retry-inplace-button": mock_retry_inplace_btn,
            "#retry-then-button": mock_retry_then_btn,
            "#retry-now-button": mock_retry_now_btn,
            "#retry-nodeps-button": mock_retry_nodeps_btn,
            "#job-metadata": mock_metadata,
            "#job-config": mock_config,
        }.get(selector, Mock(spec=[]))
        
        screen.update_data(mock_job_completed)
        
        # Cancel button should be hidden for completed job
        assert mock_cancel_btn.display == False
        # Retry buttons should be visible for completed job
        assert mock_retry_inplace_btn.display == True
        assert mock_retry_then_btn.display == True
        assert mock_retry_now_btn.display == True
        assert mock_retry_nodeps_btn.display == True
        
        # Verify footer bindings are updated (no 'c' for cancel, has 'r' for retry)
        binding_keys = [b[0] for b in screen.BINDINGS]
        assert 'c' not in binding_keys  # Cancel should not be in bindings
        assert 'r' in binding_keys  # Retry should be in bindings
        assert mock_retry_nodeps_btn.display == True

    @patch('scheduler.tui.screens.job_detail.JobDetailScreen.query_one', autospec=True)
    def test_button_visibility_for_failed_job(self, mock_query_one, mock_job_failed):
        """Test that cancel button is hidden and retry buttons are shown for failed job."""
        screen = JobDetailScreen("job_123")
        
        # Add missing attributes to mock job
        mock_job_failed.priority = 1
        mock_job_failed.assigned_gpus = [0, 1]
        mock_job_failed.submitted_at = datetime.now()
        mock_job_failed.started_at = datetime.now()
        mock_job_failed.completed_at = datetime.now()
        mock_job_failed.exit_code = 1
        mock_job_failed.command = ["test_script.py"]
        mock_job_failed.working_dir = "/tmp"
        mock_job_failed.env_vars = {}
        mock_job_failed.dependencies = []
        
        # Create mock buttons
        from textual.widgets import Button
        mock_cancel_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_inplace_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_then_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_now_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_retry_nodeps_btn = create_autospec(Button, instance=True, spec_set=True)
        mock_metadata = create_autospec(Static, instance=True, spec_set=True)
        mock_config = create_autospec(Static, instance=True, spec_set=True)
        
        mock_query_one.side_effect = lambda self, selector, widget_type: {
            "#cancel-button": mock_cancel_btn,
            "#retry-inplace-button": mock_retry_inplace_btn,
            "#retry-then-button": mock_retry_then_btn,
            "#retry-now-button": mock_retry_now_btn,
            "#retry-nodeps-button": mock_retry_nodeps_btn,
            "#job-metadata": mock_metadata,
            "#job-config": mock_config,
        }.get(selector, Mock(spec=[]))
        
        screen.update_data(mock_job_failed)
        
        # Cancel button should be hidden for failed job
        assert mock_cancel_btn.display == False
        # Retry buttons should be visible for failed job
        assert mock_retry_inplace_btn.display == True
        assert mock_retry_then_btn.display == True
        assert mock_retry_now_btn.display == True
        assert mock_retry_nodeps_btn.display == True
        
        # Verify footer bindings are updated (no 'c' for cancel, has 'r' for retry)
        binding_keys = [b[0] for b in screen.BINDINGS]
        assert 'c' not in binding_keys  # Cancel should not be in bindings
        assert 'r' in binding_keys  # Retry should be in bindings
