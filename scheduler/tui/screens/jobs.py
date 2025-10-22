from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from scheduler.api.schemas import Job

class JobsScreen(Screen):
    """Jobs list screen with filtering and sorting"""

    def compose(self) -> ComposeResult:
        """
        Compose the jobs list layout.
        
        Yields:
            Widgets for jobs list (filter controls, job table, details pane)
        """
        pass

    def update_data(self, jobs: List[Job]):
        """
        Update screen with new data.
        
        Args:
            jobs: List of Job instances
        """
        pass

    def on_job_selected(self, job_id: str):
        """
        Handle job selection.
        
        Args:
            job_id: Selected job ID
        """
        pass

    def filter_jobs(self, filter_text: str):
        """
        Filter jobs by search text.
        
        Args:
            filter_text: Text to filter by
        """
        pass
