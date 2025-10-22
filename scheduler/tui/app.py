from textual.app import App,ComposeResult


from scheduler.api.client import SchedulerClient

class SchedulerTUI(App):
    """Main Textual TUI application"""

    def __init__(self, client: SchedulerClient):
        """
        Initialize TUI application.
        
        Args:
            client: SchedulerClient instance
        """
        pass

    def compose(self) -> ComposeResult:
        """
        Compose the UI layout.
        
        Returns:
            Yields widgets that compose the UI
        """
        pass

    def on_mount(self):
        """
        Called when app is mounted.
        Sets up timers and initial data fetch.
        """
        pass

    def refresh_data(self):
        """
        Refresh data from head node.
        """
        pass

    def action_quit(self):
        """
        Quit the application (bound to 'q').
        """
        pass

    def action_show_nodes(self):
        """
        Switch to nodes view (bound to 'n').
        """
        pass

    def action_show_jobs(self):
        """
        Switch to jobs view (bound to 'j').
        """
        pass

    def action_show_gpus(self):
        """
        Switch to GPUs view (bound to 'g').
        """
        pass

    def action_help(self):
        """
        Show help screen (bound to 'h').
        """
        pass
