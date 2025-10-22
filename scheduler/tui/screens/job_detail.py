from textual.screen import Screen
from textual.app import ComposeResult
from scheduler.api.schemas import Job

class JobDetailScreen(Screen):
    """Single job detail screen"""

    def __init__(self, job_id: str):
        """
        Initialize job detail screen.

        Args:
            job_id: Job ID to display
        """
        super().__init__()
        self.job_id = job_id

    def compose(self) -> ComposeResult:
        """
        Compose the job detail layout.

        Yields:
            Widgets for job details (metadata, logs preview, actions)
        """
        pass

    def update_data(self, job: Job):
        """
        Update screen with new job data.

        Args:
            job: Job instance
        """
        pass

    def action_view_logs(self):
        """
        View full job logs.

        Bound to 'l' key.
        """
        pass

    def action_cancel_job(self):
        """
        Cancel the job.

        Bound to 'c' key.
        Shows confirmation dialog.
        """
        pass

