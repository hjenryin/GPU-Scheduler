from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, Button
from textual.containers import Container, Horizontal, VerticalScroll
from scheduler.core import Job  # Import from peer submodule's public API
from scheduler.tui.utils import format_runtime


def process_log_escape_sequences(logs: str) -> str:
    """
    Process escape sequences in log strings to render them properly.
    
    Args:
        logs: Raw log string that may contain literal escape sequences
        
    Returns:
        Processed log string with escape sequences converted to actual characters
    """
    if not logs:
        return logs
    # Replace literal \n with actual newlines and handle other escape sequences
    return logs.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')


class JobDetailScreen(Screen):
    """Single job detail screen"""

    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("l", "view_logs", "Logs"),
        ("c", "cancel_job", "Cancel"),
        ("q", "quit", "Quit"),
    ]

    def __init__(self, job_id: str):
        """
        Initialize job detail screen.

        Args:
            job_id: Job ID to display
        """
        super().__init__()
        self.job_id = job_id
        self.job_data = None

    def compose(self) -> ComposeResult:
        """
        Compose the job detail layout.

        Yields:
            Widgets for job details (metadata, logs preview, actions)
        """
        yield Header()
        yield VerticalScroll(
            Container(
                Static(f"Job Details: {self.job_id}", id="job-detail-title"),
                Static("", id="job-metadata"),
                Static("Job Configuration", id="job-config-header"),
                Static("", id="job-config"),
                Static("Logs Preview (last 20 lines)", id="logs-header"),
                Static("Loading logs...", id="logs-preview"),
                Horizontal(
                    Button("View Full Logs (l)", id="logs-button", variant="primary"),
                    Button("Cancel Job (c)", id="cancel-button", variant="error"),
                    Button("Back (esc)", id="back-button"),
                    id="action-buttons",
                ),
                id="job-detail-container",
            )
        )
        yield Footer()

    def on_mount(self):
        """Fetch job data when screen is mounted."""
        # Get the client from the app
        if hasattr(self.app, "client"):
            try:
                job = self.app.client.get_job(self.job_id)
                self.update_data(job)

                # Try to fetch logs
                try:
                    logs = self.app.client.get_job_logs(
                        self.job_id, lines=20, stderr=False
                    )
                    # Process logs to handle escape sequences properly
                    if logs:
                        processed_logs = process_log_escape_sequences(logs)
                        self.query_one("#logs-preview", Static).update(processed_logs)
                    else:
                        self.query_one("#logs-preview", Static).update("No logs available yet.")
                except Exception as e:
                    self.query_one("#logs-preview", Static).update(
                        f"Could not fetch logs: {e}"
                    )
            except Exception as e:
                self.query_one("#job-metadata", Static).update(
                    f"Error loading job: {e}"
                )

    def update_data(self, job: Job):
        """
        Update screen with new job data.

        Args:
            job: Job instance
        """
        self.job_data = job

        # Update metadata
        submitted_time = (
            job.submitted_at.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(job, "submitted_at") and job.submitted_at
            else "N/A"
        )
        started_time = (
            job.started_at.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(job, "started_at") and job.started_at
            else "N/A"
        )
        completed_time = (
            job.completed_at.strftime("%Y-%m-%d %H:%M:%S")
            if hasattr(job, "completed_at") and job.completed_at
            else "N/A"
        )

        # Format GPU list
        gpu_list = (
            ", ".join(map(str, job.assigned_gpus))
            if hasattr(job, "assigned_gpus") and job.assigned_gpus
            else "Not assigned"
        )
        # Format runtime
        runtime_str = (
            format_runtime(job.runtime)
            if hasattr(job, "runtime")
            else "N/A"
        )
        # Format exit code
        exit_code_str = (
            str(job.exit_code)
            if hasattr(job, "exit_code") and job.exit_code is not None
            else "N/A"
        )

        metadata = (
            f"Job ID:      {job.job_id}\n"
            f"Name:        {job.name or 'N/A'}\n"
            f"Status:      {job.status.value}\n"
            f"Priority:    {job.priority}\n"
            f"Node:        {job.assigned_node or 'Not assigned'}\n"
            f"GPUs:        {gpu_list}\n"
            f"Submitted:   {submitted_time}\n"
            f"Started:     {started_time}\n"
            f"Completed:   {completed_time}\n"
            f"Runtime:     {runtime_str}\n"
            f"Exit Code:   {exit_code_str}"
        )
        self.query_one("#job-metadata", Static).update(metadata)

        # Update configuration
        config = (
            f"Script:      {job.script}\n"
            f"Arguments:   {' '.join(job.script_args) if job.script_args else 'None'}\n"
            f"Working Dir: {job.working_dir or 'Default'}\n"
            f"Environment: {len(job.env_vars) if job.env_vars else 0} variables\n"
            f"Requirements: {str(job.requirements) if job.requirements else '?'}"
        )
        if job.requirements and job.requirements.alternatives:
            alt_str = ", ".join(
                [
                    f"{node or 'any'}:{ngpus}"
                    for node, ngpus in job.requirements.alternatives
                ]
            )
            config += f" ({alt_str})"

        if job.dependencies:
            config += f"\nDependencies: {', '.join(job.dependencies)}"

        self.query_one("#job-config", Static).update(config)

    def action_view_logs(self):
        """
        View full job logs.

        Bound to 'l' key.
        """
        if hasattr(self.app, "client"):
            try:
                # Fetch full logs
                logs = self.app.client.get_job_logs(
                    self.job_id, lines=None, stderr=False
                )
                stderr_logs = self.app.client.get_job_logs(
                    self.job_id, lines=None, stderr=True
                )

                # Process logs to handle escape sequences
                stdout = logs if logs else "No stdout logs"
                stderr = stderr_logs if stderr_logs else "No stderr logs"
                
                # Apply escape sequence processing
                stdout = process_log_escape_sequences(stdout)
                stderr = process_log_escape_sequences(stderr)
                
                full_logs = "=== STDOUT ===\n" + stdout
                full_logs += "\n\n=== STDERR ===\n" + stderr

                self.query_one("#logs-preview", Static).update(full_logs)
                self.query_one("#logs-header", Static).update("Full Logs")
            except Exception as e:
                self.query_one("#logs-preview", Static).update(
                    f"Error fetching logs: {e}"
                )

    def action_cancel_job(self):
        """
        Cancel the job.

        Bound to 'c' key.
        Shows confirmation dialog.
        """
        if self.job_data and self.job_data.status.value in ["pending", "running"]:
            if hasattr(self.app, "client"):
                try:
                    self.app.client.cancel_job(self.job_id)
                    # Refresh job data
                    job = self.app.client.get_job(self.job_id)
                    self.update_data(job)
                    self.app.notify(f"Job {self.job_id} cancelled successfully")
                except Exception as e:
                    self.app.notify(f"Error cancelling job: {e}", severity="error")
        else:
            self.app.notify(
                "Job cannot be cancelled (not pending or running)", severity="warning"
            )

    def on_button_pressed(self, event):
        """Handle button presses."""
        if event.button.id == "logs-button":
            self.action_view_logs()
        elif event.button.id == "cancel-button":
            self.action_cancel_job()
        elif event.button.id == "back-button":
            self.app.pop_screen()
