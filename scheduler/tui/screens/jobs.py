from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Input
from textual.containers import Container, Horizontal
from textual import events
from scheduler.core import Job  # Import from peer submodule's public API
from scheduler.tui.utils import format_runtime


class JobsScreen(Screen):
    """Jobs list screen with filtering and sorting"""

    BINDINGS = [
        ("n", "switch_to_cluster", "Cluster"),
        ("g", "switch_to_gpus", "GPUs"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
        ("1", "filter_pending", "Pending"),
        ("2", "filter_running", "Running"),
        ("3", "filter_completed", "Completed"),
        ("4", "filter_failed", "Failed"),
        ("5", "filter_all", "All"),
        ("/", "focus_search", "Search"),
        ("escape", "switch_to_cluster", "Back"),
        ("enter", "show_job_detail", "Details"),
    ]

    def __init__(self):
        super().__init__()
        self.jobs_data: List[Job] = []
        self.current_filter: str = "all"
        self.search_text: str = ""

    def compose(self) -> ComposeResult:
        """
        Compose the jobs list layout.

        Yields:
            Widgets for jobs list (filter controls, job table, details pane)
        """
        yield Header()
        yield Container(
            Static("JOBS", id="jobs-header"),
            Horizontal(
                Static("Filter: ", id="filter-label"),
                Static("[All Jobs]", id="filter-status"),
                Static("  Sort: [Submitted]", id="sort-status"),
                id="filter-bar",
            ),
            Input(placeholder="Search jobs (press / to focus)...", id="search-input"),
            DataTable(id="jobs-table"),
            id="jobs-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up table when screen is mounted."""
        jobs_table = self.query_one("#jobs-table", DataTable)
        jobs_table.add_columns(
            "Job ID", "Name", "Status", "Node", "GPUs", "Runtime", "Submitted"
        )
        jobs_table.cursor_type = "row"

    def update_data(self, jobs: List[Job]):
        """
        Update screen with new data.

        Args:
            jobs: List of Job instances
        """
        self.jobs_data = jobs
        self._refresh_table()

    def _refresh_table(self):
        """Refresh the jobs table with current filter and search."""
        # Apply filters
        filtered_jobs = self.jobs_data

        # Apply status filter
        if self.current_filter != "all":
            filtered_jobs = [
                j for j in filtered_jobs if j.status.value == self.current_filter
            ]

        # Apply search filter
        if self.search_text:
            search_lower = self.search_text.lower()
            filtered_jobs = [
                j
                for j in filtered_jobs
                if search_lower in j.job_id.lower()
                or (j.name and search_lower in j.name.lower())
                or (j.assigned_node and search_lower in j.assigned_node.lower())
            ]

        # Update table
        jobs_table = self.query_one("#jobs-table", DataTable)
        jobs_table.clear()
        for job in filtered_jobs:
            submitted_time = (
                job.submitted_at.strftime("%Y-%m-%d %H:%M")
                if hasattr(job, "submitted_at") and job.submitted_at
                else "N/A"
            )
            jobs_table.add_row(
                job.job_id,
                job.name or "N/A",
                job.status.value,
                job.assigned_node or "-",
                str(job.requirements) if job.requirements else "?",
                format_runtime(job.runtime) if hasattr(job, "runtime") else "-",
                submitted_time,
            )

    def on_input_changed(self, event):
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_text = event.value
            self._refresh_table()

    def on_data_table_row_selected(self, event):
        """Handle row selection in jobs table."""
        if event.data_table.id == "jobs-table":
            row_data = event.data_table.get_row(event.row_key)
            job_id = str(row_data[0])
            self.on_job_selected(job_id)

    def on_job_selected(self, job_id: str):
        """
        Handle job selection.

        Args:
            job_id: Selected job ID
        """
        # This will be handled by pushing a JobDetailScreen
        from scheduler.tui.screens.job_detail import JobDetailScreen

        self.app.push_screen(JobDetailScreen(job_id))

    def filter_jobs(self, filter_text: str):
        """
        Filter jobs by search text.

        Args:
            filter_text: Text to filter by
        """
        self.search_text = filter_text
        self._refresh_table()

    def action_filter_pending(self):
        """Filter to show only pending jobs."""
        self.current_filter = "pending"
        self.query_one("#filter-status", Static).update("[Pending]")
        self._refresh_table()

    def action_filter_running(self):
        """Filter to show only running jobs."""
        self.current_filter = "running"
        self.query_one("#filter-status", Static).update("[Running]")
        self._refresh_table()

    def action_filter_completed(self):
        """Filter to show only completed jobs."""
        self.current_filter = "completed"
        self.query_one("#filter-status", Static).update("[Completed]")
        self._refresh_table()

    def action_filter_failed(self):
        """Filter to show only failed jobs."""
        self.current_filter = "failed"
        self.query_one("#filter-status", Static).update("[Failed]")
        self._refresh_table()

    def action_filter_all(self):
        """Show all jobs."""
        self.current_filter = "all"
        self.query_one("#filter-status", Static).update("[All Jobs]")
        self._refresh_table()

    def action_focus_search(self):
        """Focus the search input."""
        self.query_one("#search-input", Input).focus()

    def action_show_job_detail(self):
        """Show detail for currently selected job."""
        jobs_table = self.query_one("#jobs-table", DataTable)
        if jobs_table.cursor_row is not None:
            row_key = jobs_table.cursor_row
            row_data = jobs_table.get_row(row_key)
            job_id = str(row_data[0])
            self.on_job_selected(job_id)

    def on_key(self, event: events.Key) -> None:
        """Handle key events, especially escape when input is focused."""
        if event.key == "escape":
            # Check if the search input is focused
            search_input = self.query_one("#search-input", Input)
            if search_input.has_focus:
                # Blur the input instead of going back
                search_input.blur()
                event.prevent_default()
                event.stop()
            # If input is not focused, let the default escape binding handle it
