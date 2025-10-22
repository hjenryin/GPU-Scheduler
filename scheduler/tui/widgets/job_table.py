from typing import List, Optional
from textual.widgets import DataTable
from scheduler.core import Job, JobStatus


class JobTable(DataTable):
    """Custom DataTable for displaying job information"""

    def __init__(self, **kwargs):
        """
        Initialize job table widget.
        
        Args:
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self._setup_columns()

    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Job ID, Name, Status, Node, GPUs, Runtime
        """
        pass

    def update_jobs(self, jobs: List[Job]):
        """
        Update table with job data.
        
        Args:
            jobs: List of Job instances
        """
        pass

    def filter_by_status(self, status: Optional[JobStatus] = None):
        """
        Filter jobs by status.
        
        Args:
            status: JobStatus to filter by (None for all)
        """
        pass

    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (job ID)
        """
        pass
