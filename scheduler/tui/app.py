from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Header, Footer
import logging
from typing import Optional

from scheduler.api import SchedulerClient
from scheduler.core import Config
from scheduler.tui.screens import ClusterScreen, NodesScreen, JobsScreen, GPUsScreen, StatusScreen

logger = logging.getLogger(__name__)


class SchedulerTUI(App):
    """Main Textual TUI application"""
    
    # Class attributes with type annotations and defaults for proper mocking with spec_set
    client: SchedulerClient = None  # type: ignore
    config: Optional[Config] = None
    refresh_interval: float = 2.0
    nodes_data: list = []
    jobs_data: list = []

    CSS = """
    Screen {
        background: $surface;
    }

    DataTable {
        height: auto;
    }

    #cluster-summary, #gpu-summary, #node-detail-info, #job-metadata, #job-config {
        margin: 1;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }

    #node-header, #gpu-header, #job-header, #nodes-list-header, #gpu-detail-header,
    #jobs-detail-header, #jobs-header, #gpu-overview-header, #all-gpus-header,
    #job-detail-title, #job-config-header, #logs-header, #status-summary-header,
    #head-logs-header, #worker-logs-header {
        text-style: bold;
        background: $primary;
        color: $text;
        padding: 1;
        margin-bottom: 1;
    }

    #status-summary {
        margin: 1;
        padding: 1;
        background: $panel;
        border: solid $primary;
    }

    #filter-bar {
        height: 1;
        margin: 1 0;
    }

    #search-input {
        margin: 1;
        width: 100%;
    }

    #action-buttons {
        height: auto;
        margin: 1;
        align: center middle;
    }

    #action-buttons Button {
        margin: 0 1;
        height: 4;
        min-width: 12;
        max-width: 16;
        padding: 0 1;
    }

    Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", priority=True),
        Binding("h", "help", "Help"),
        Binding("r", "refresh", "Refresh"),
        Binding("c", "switch_to_cluster", "Cluster"),
        Binding("n", "switch_to_nodes", "Nodes"),
        Binding("j", "switch_to_jobs", "Jobs"),
        Binding("g", "switch_to_gpus", "GPUs"),
        Binding("s", "switch_to_status", "Status"),
    ]

    SCREENS = {
        "cluster": ClusterScreen,
        "nodes": NodesScreen,
        "jobs": JobsScreen,
        "gpus": GPUsScreen,
        "status": StatusScreen,
    }

    def __init__(self, client: SchedulerClient):
        """
        Initialize TUI application.

        Args:
            client: SchedulerClient instance
        """
        super().__init__()
        self.client = client
        self.config = client.config if hasattr(client, 'config') else None
        self.refresh_interval = 2.0  # seconds
        self.nodes_data = []
        self.jobs_data = []
        
        # Default thresholds if config not available
        if self.config:
            self.util_threshold = self.config.worker.gpu_util_threshold
            self.mem_threshold = self.config.worker.gpu_mem_threshold
            self.stable_time = getattr(self.config.worker, 'gpu_stable_time', 120)
        else:
            self.util_threshold = 10.0
            self.mem_threshold = 10.0
            self.stable_time = 120

    def compose(self) -> ComposeResult:
        """
        Compose the UI layout.

        Returns:
            Yields widgets that compose the UI
        """
        # For screen-based apps, screens handle their own Header/Footer
        # Return empty to satisfy the generator protocol
        return
        yield  # Make this a generator

    def on_mount(self):
        """
        Called when app is mounted.
        Sets up timers and initial data fetch.
        """
        # Push the initial screen
        self.push_screen("cluster")
        
        # Set up periodic refresh
        self.set_interval(self.refresh_interval, self.refresh_data)

        # Initial data fetch
        self.refresh_data()

    def refresh_data(self):
        """
        Refresh data from head node.
        """
        try:
            # Fetch data from API
            self.nodes_data = self.client.list_nodes()
            self.jobs_data = self.client.list_jobs()
            
            logger.info(f"Fetched {len(self.nodes_data)} nodes and {len(self.jobs_data)} jobs")

            # Update current screen if available
            try:
                current_screen = self.screen
                logger.info(f"Current screen type: {type(current_screen).__name__}")
                
                if isinstance(current_screen, ClusterScreen):
                    logger.info("Updating ClusterScreen data")
                    current_screen.update_data(self.nodes_data, self.jobs_data, 
                                              self.util_threshold, self.mem_threshold, self.stable_time)
                elif isinstance(current_screen, NodesScreen):
                    logger.info("Updating NodesScreen data")
                    current_screen.update_data(self.nodes_data, self.jobs_data,
                                              self.util_threshold, self.mem_threshold, self.stable_time)
                elif isinstance(current_screen, JobsScreen):
                    logger.info("Updating JobsScreen data")
                    current_screen.update_data(self.jobs_data)
                elif isinstance(current_screen, GPUsScreen):
                    logger.info("Updating GPUsScreen data")
                    current_screen.update_data(self.nodes_data,
                                              self.util_threshold, self.mem_threshold, self.stable_time)
                elif isinstance(current_screen, StatusScreen):
                    logger.info("Updating StatusScreen data")
                    current_screen.update_data(self.client)
            except Exception as screen_error:
                # Screen not available (e.g., during testing or before app is mounted)
                logger.debug(f"Could not update screen: {screen_error}", exc_info=True)

        except Exception as e:
            logger.error(f"Error refreshing data: {e}", exc_info=True)
            self.notify(f"Error refreshing data: {e}", severity="error")

    def action_quit(self):
        """
        Quit the application (bound to 'q').
        """
        self.exit()

    def action_switch_to_cluster(self):
        """
        Switch to cluster overview (bound to 'c' from other screens, escape for back).
        """
        self.switch_screen("cluster")
        self.refresh_data()

    def action_switch_to_nodes(self):
        """
        Switch to nodes view (bound to 'n').
        """
        self.switch_screen("nodes")
        self.refresh_data()

    def action_switch_to_jobs(self):
        """
        Switch to jobs view (bound to 'j').
        """
        self.switch_screen("jobs")
        self.refresh_data()

    def action_switch_to_gpus(self):
        """
        Switch to GPUs view (bound to 'g').
        """
        self.switch_screen("gpus")
        self.refresh_data()

    def action_switch_to_status(self):
        """
        Switch to Status view (bound to 's').
        """
        self.switch_screen("status")
        self.refresh_data()

    def action_refresh(self):
        """
        Manually refresh data (bound to 'r').
        """
        self.notify("Refreshing data...")
        self.refresh_data()

    def action_help(self):
        """
        Show help screen (bound to 'h').
        """
        help_text = """
# GPU Scheduler TUI Help

## Global Keybindings:
- **q**: Quit application
- **h**: Show this help
- **r**: Manually refresh data
- **c**: Switch to Cluster view
- **n**: Switch to Nodes view
- **j**: Switch to Jobs view
- **g**: Switch to GPUs view
- **s**: Switch to Status view
- **Esc**: Go back to cluster overview

## Cluster Overview:
- View summary of all nodes, GPUs, and active jobs
- Shows GPU utilization bars
- Displays active jobs

## Nodes View:
- Navigate through nodes using arrow keys
- Select a node to see detailed GPU information
- View running jobs on each node

## Jobs View:
- **1-5**: Filter by status (Pending/Running/Completed/Failed/All)
- **/**: Focus search box
- **Enter**: View job details
- Use search box to filter by job ID, name, or node

## Job Detail:
- **l**: View full logs
- **c**: Cancel job (if pending/running)
- **Esc**: Go back

## GPUs View:
- View all GPUs across all nodes
- See utilization, memory, temperature, power
- Identify which job is using each GPU

## Status View:
- View warnings and errors from head node
- View warnings and errors from local worker (if running)
- Collapsed duplicate messages with counts
- Most recent logs first

Data auto-refreshes every 2 seconds.
        """
        self.notify(help_text.strip(), timeout=20)


def run_tui(client: Optional[SchedulerClient] = None, address: Optional[str] = None):
    """
    Run the TUI application.

    Args:
        client: SchedulerClient instance (if None, creates one)
        address: Head node address (used if client is None)
    """
    if client is None:
        client = SchedulerClient(address=address)

    app = SchedulerTUI(client)
    
    # Enable dev mode for better debugging - logs will show in textual console
    # Run with: textual console then in another terminal run: textual run --dev scheduler.tui.app:run_tui
    try:
        app.run()
    except Exception as e:
        logger.error(f"Error running TUI: {e}", exc_info=True)
        raise
