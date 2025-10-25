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
        self._columns_setup = False

    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Job ID, Name, Status, Node, GPUs, Runtime
        """
        if not self._columns_setup:
            self.add_columns("Job ID", "Name", "Status", "Node", "GPUs", "Runtime")
            self.cursor_type = "row"
            self._columns_setup = True

    def update_jobs(self, jobs: List[Job]):
        """
        Update table with job data.
        
        Args:
            jobs: List of Job instances
        """
        # Ensure columns are set up
        self._setup_columns()
        
        # Store all jobs for filtering
        self._all_jobs = jobs
        
        # Apply status filter if set
        filtered_jobs = jobs
        if hasattr(self, '_status_filter') and self._status_filter is not None:
            filtered_jobs = [job for job in jobs if job.status == self._status_filter]
        
        self.clear()
        for job in filtered_jobs:
            from scheduler.tui.utils import format_runtime
            self.add_row(
                job.job_id,
                job.name or "N/A",
                job.status.value,
                job.assigned_node or "-",
                str(job.requirements.num_gpus) if job.requirements else "?",
                format_runtime(job.runtime) if hasattr(job, 'runtime') else "-"
            )

    def filter_by_status(self, status: Optional[JobStatus] = None):
        """
        Filter jobs by status.
        
        Args:
            status: JobStatus to filter by (None for all)
        """
        # Store the filter status for use in update_jobs
        self._status_filter = status
        # Re-apply the filter to current jobs
        if hasattr(self, '_all_jobs'):
            self.update_jobs(self._all_jobs)

    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (job ID)
        """
        # Emit a custom event that can be handled by parent components
        self.post_message(self.JobSelected(row_key))
    
    class JobSelected:
        """Event emitted when a job is selected."""
        def __init__(self, job_id: str):
            self.job_id = job_id
