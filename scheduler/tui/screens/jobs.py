from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable, Input
from textual.containers import Container, Horizontal, VerticalScroll
from textual import events
from scheduler.core import Job  # Import from peer submodule's public API
from scheduler.core import format_eta_display
from scheduler.tui.utils import format_runtime


class JobsScreen(Screen):
    """Jobs list screen with filtering and sorting"""

    BINDINGS = [
        ("c", "switch_to_cluster", "Cluster"),
        ("n", "switch_to_nodes", "Nodes"),
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
        self._last_table_data: List[tuple] = []  # Track last rendered data to detect changes
        self._initial_render: bool = True  # Flag to ensure first render always happens

    def compose(self) -> ComposeResult:
        """
        Compose the jobs list layout.

        Yields:
            Widgets for jobs list (filter controls, job table, details pane)
        """
        yield Header()
        yield Container(
            VerticalScroll(
                Static("JOBS", id="jobs-header"),
                Horizontal(
                    Static("Filter: ", id="filter-label"),
                    Static("[All Jobs]", id="filter-status"),
                    Static("  Sort: [Submitted]", id="sort-status"),
                    id="filter-bar",
                ),
                Input(placeholder="Search jobs (press / to focus)...", id="search-input"),
                DataTable(id="jobs-table"),
                id="jobs-scroll"
            ),
            id="jobs-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up table when screen is mounted."""
        jobs_table = self.query_one("#jobs-table", DataTable)
        jobs_table.add_columns(
            "Name", "Status", "Node", "GPUs", "Runtime", "ETA", "Submitted"
        )
        jobs_table.cursor_type = "row"

    def on_screen_resume(self):
        """Called when screen becomes active. Force a refresh."""
        # Reset initial render flag to force a refresh when returning to this screen
        self._initial_render = True
        self._refresh_table_if_changed()

    def update_data(self, jobs: List[Job]):
        """
        Update screen with new data.

        Args:
            jobs: List of Job instances
        """
        self.jobs_data = jobs
        self._refresh_table_if_changed()

    def _truncate_text(self, text: str, max_len: int) -> str:
        """Truncate text with ellipsis if it exceeds max length."""
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."

    def _calculate_column_widths(self, filtered_jobs: List[Job]) -> tuple:
        """
        Calculate actual column widths needed based on data and terminal width.
        Priority order for truncation:
        1. Show everything if possible
        2. Truncate GPUs first (down to min 15 chars)
        3. Then truncate Name (down to min 10 chars)
        
        Returns (name_width, gpus_width)
        """
        try:
            terminal_width = self.app.size.width
            
            # Calculate actual max widths needed for each column from the data
            max_status = max((len(j.status.value) for j in filtered_jobs), default=7) if filtered_jobs else 7
            max_node = max((len(j.assigned_node or "-") for j in filtered_jobs), default=4) if filtered_jobs else 4
            max_gpus_data = max((len(str(j.requirements) if j.requirements else "?") for j in filtered_jobs), default=4) if filtered_jobs else 4
            max_name_data = max((len(j.name or "N/A") for j in filtered_jobs), default=4) if filtered_jobs else 4
            max_runtime = 8  # Runtime format is relatively fixed (e.g., "12h 34m")
            max_eta = 8  # ETA format is relatively fixed
            max_submitted = 16  # Date format is fixed (YYYY-MM-DD HH:MM)
            
            # Add column headers into consideration
            max_status = max(max_status, len("Status"))
            max_node = max(max_node, len("Node"))
            max_gpus_data = max(max_gpus_data, len("GPUs"))
            max_name_data = max(max_name_data, len("Name"))
            max_runtime = max(max_runtime, len("Runtime"))
            max_eta = max(max_eta, len("ETA"))
            max_submitted = max(max_submitted, len("Submitted"))
            
            # DataTable adds padding (approximately 3 chars per column)
            num_columns = 7
            padding = num_columns * 3
            borders = 2
            
            # Calculate truly fixed columns (everything except Name and GPUs)
            fixed_width = max_status + max_node + max_runtime + max_eta + max_submitted + padding + borders
            
            # Available space for Name and GPUs combined
            available_for_flexible = terminal_width - fixed_width
            
            # Minimum constraints
            min_gpus_width = 15
            min_name_width = 10
            
            # Strategy: Try to show everything, then truncate GPUs, then Name
            # Ideal case: both columns show full data
            ideal_gpus = max_gpus_data
            ideal_name = max_name_data
            ideal_total = ideal_gpus + ideal_name
            
            if available_for_flexible >= ideal_total:
                # Best case: show everything
                return (ideal_name, ideal_gpus)
            
            # Not enough space, need to truncate
            # First, try truncating GPUs down to minimum
            if available_for_flexible >= min_gpus_width + ideal_name:
                # We can show full name, just truncate GPUs
                gpus_width = available_for_flexible - ideal_name
                gpus_width = max(min_gpus_width, gpus_width)
                return (ideal_name, gpus_width)
            
            # Still not enough, GPUs is at minimum, need to truncate Name too
            gpus_width = min_gpus_width
            name_width = available_for_flexible - gpus_width
            name_width = max(min_name_width, name_width)
            
            return (name_width, gpus_width)
            
        except Exception:
            # Fallback to reasonable defaults
            return (30, 15)

    def _refresh_table_if_changed(self):
        """Refresh the jobs table only if data has changed."""
        try:
            jobs_table = self.query_one("#jobs-table", DataTable)
        except Exception:
            # Table not yet mounted, skip
            return
            
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
                or (j.command and search_lower in " ".join(j.command).lower())
            ]

        # Calculate dynamic column widths based on actual data and terminal size
        name_width, gpus_width = self._calculate_column_widths(filtered_jobs)

        # Build new table data
        new_table_data = []
        for job in filtered_jobs:
            submitted_time = (
                job.submitted_at.strftime("%Y-%m-%d %H:%M")
                if hasattr(job, "submitted_at") and job.submitted_at
                else "N/A"
            )
            eta_display = format_eta_display(job.eta)
            if eta_display and eta_display.endswith("s"):
                parts = eta_display.split()
                if len(parts) > 1 and parts[-1].endswith("s"):
                    eta_display = " ".join(parts[:-1])
                elif len(parts) == 1 and parts[0].endswith("s"):
                    eta_display = "<1m"
            runtime_display = format_runtime(job.get_runtime())
            
            # Use dynamically calculated width for GPUs column
            gpus_text = str(job.requirements) if job.requirements else "?"
            gpus_display = self._truncate_text(gpus_text, gpus_width)
            
            # Store full name, will truncate dynamically when rendering
            name_display = job.name or "N/A"
            
            status_display = f"{job.status.value} (restarted)" if getattr(job, 'restarted', False) else job.status.value
            
            new_table_data.append((
                job.job_id,
                name_display,
                status_display,
                job.assigned_node or "-",
                gpus_display,
                runtime_display,
                eta_display,
                submitted_time,
            ))

        # Check if data has actually changed (skip check on initial render)
        if not self._initial_render and new_table_data == self._last_table_data:
            # No changes, skip refresh to preserve table position
            return

        # Data has changed or this is the initial render, update the table
        self._initial_render = False
        self._last_table_data = new_table_data
        jobs_table.clear()
        
        for row_data in new_table_data:
            # Apply name truncation based on dynamically calculated width
            name = row_data[1]
            truncated_name = self._truncate_text(name, name_width)
            
            jobs_table.add_row(
                truncated_name,  # name (dynamically truncated)
                row_data[2],  # status
                row_data[3],  # assigned_node
                row_data[4],  # gpus (already truncated)
                row_data[5],  # runtime
                row_data[6],  # eta
                row_data[7],  # submitted_time
                key=row_data[0],  # Use job_id as the row key
            )

    def _refresh_table(self):
        """Force refresh the jobs table (used for filter/search changes)."""
        # Clear the cache to force a refresh
        self._last_table_data = []
        self._initial_render = True  # Treat as initial render to force update
        self._refresh_table_if_changed()

    def on_input_changed(self, event):
        """Handle search input changes."""
        if event.input.id == "search-input":
            self.search_text = event.value
            self._refresh_table()

    def on_data_table_row_selected(self, event):
        """Handle row selection in jobs table."""
        if event.data_table.id == "jobs-table":
            try:
                # Use key directly to identify job_id
                job_id = str(event.row_key.value) if hasattr(event.row_key, "value") else str(event.row_key)
                self.on_job_selected(job_id)
            except Exception:
                # Row doesn't exist anymore, ignore
                pass

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
            job_id = str(row_key.value) if hasattr(row_key, "value") else str(row_key)
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
            # Otherwise, let the default escape binding handle navigation
