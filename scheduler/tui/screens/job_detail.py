from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, Button, TextArea
from textual.containers import Container, Horizontal, VerticalScroll
from scheduler.core import Job  # Import from peer submodule's public API
from scheduler.core import format_eta_display
from scheduler.tui.utils import format_runtime
from rich.text import Text


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
    # Also handle literal ANSI escape sequences like \\u001b -> \u001b
    processed = logs.replace('\\n', '\n').replace('\\t', '\t').replace('\\r', '\r')
    # Decode unicode escape sequences (e.g., \u001b[91m -> actual ANSI codes)
    try:
        processed = processed.encode().decode('unicode_escape')
    except:
        pass  # If decoding fails, keep the original
    return processed


class JobDetailScreen(Screen):
    """Single job detail screen"""

    # Base bindings that are always available
    BINDINGS = [
        ("escape", "pop_screen", "Back"),
        ("l", "view_logs", "Logs"),
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
        self._cancel_binding = ("c", "cancel_job", "Cancel")
        self._retry_binding = ("r", "show_retry_menu", "Retry")

    def compose(self) -> ComposeResult:
        """
        Compose the job detail layout.

        Yields:
            Widgets for job details (metadata, logs preview, actions)
        """
        yield Header()
        yield Container(
            VerticalScroll(
                Static(f"Job Details: {self.job_id}", id="job-detail-title"),
                Static("", id="job-metadata"),
                Static("Job Configuration", id="job-config-header"),
                Static("", id="job-config"),
                Static("STDOUT Preview (last 20 lines)", id="stdout-header"),
                Container(
                    TextArea(
                        "",
                        id="stdout-preview",
                        read_only=True,
                        show_line_numbers=False,
                    ),
                    id="stdout-container",
                ),
                Static("STDERR Preview (last 20 lines)", id="stderr-header"),
                Container(
                    TextArea(
                        "",
                        id="stderr-preview",
                        read_only=True,
                        show_line_numbers=False,
                    ),
                    id="stderr-container",
                ),
                Horizontal(
                    Button("View Full Logs (l)", id="logs-button", variant="primary"),
                    Button("Cancel Job (c)", id="cancel-button", variant="error"),
                    Button("Back (esc)", id="back-button"),
                    Button("Retry\nIn-Place", id="retry-inplace-button", variant="success"),
                    Button("Retry\n--then", id="retry-then-button", variant="success"),
                    Button("Retry\n--now", id="retry-now-button", variant="success"),
                    Button("Retry\n--no-deps", id="retry-nodeps-button", variant="success"),
                    id="action-buttons",
                ),
                id="job-scroll"
            ),
            id="job-detail-container",
        )
        yield Footer()

    def on_mount(self):
        """Fetch job data when screen is mounted."""
        # Set height for the logs containers programmatically
        stdout_container = self.query_one("#stdout-container", Container)
        stdout_container.styles.height = 13  # 13 lines height
        stdout_container.styles.border = ("solid", "cyan")
        
        stderr_container = self.query_one("#stderr-container", Container)
        stderr_container.styles.height = 13  # 13 lines height
        stderr_container.styles.border = ("solid", "red")

        # Get the client from the app
        if hasattr(self.app, "client"):
            try:
                job = self.app.client.get_job(self.job_id)
                self.update_data(job)

                # Only fetch logs if job is not pending or cancelled
                if job.status.value not in ["pending", "cancelled"]:
                    # Try to fetch stdout logs
                    try:
                        stdout_logs = self.app.client.get_job_logs(
                            self.job_id, lines=20, stderr=False
                        )
                        # Process logs to handle escape sequences properly
                        stdout_widget = self.query_one("#stdout-preview", TextArea)
                        if stdout_logs:
                            processed_logs = process_log_escape_sequences(stdout_logs)
                            stdout_widget.load_text(processed_logs)
                        else:
                            stdout_widget.load_text("No stdout logs available yet.")
                    except Exception as e:
                        stdout_widget = self.query_one("#stdout-preview", TextArea)
                        stdout_widget.load_text(f"Could not fetch stdout logs: {e}")
                    
                    # Try to fetch stderr logs
                    try:
                        stderr_logs = self.app.client.get_job_logs(
                            self.job_id, lines=20, stderr=True
                        )
                        # Process logs to handle escape sequences properly
                        stderr_widget = self.query_one("#stderr-preview", TextArea)
                        if stderr_logs:
                            processed_logs = process_log_escape_sequences(stderr_logs)
                            stderr_widget.load_text(processed_logs)
                        else:
                            stderr_widget.load_text("No stderr logs available yet.")
                    except Exception as e:
                        stderr_widget = self.query_one("#stderr-preview", TextArea)
                        stderr_widget.load_text(f"Could not fetch stderr logs: {e}")
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

        # Show/hide buttons based on job status
        can_retry = job.status.value in ["failed", "cancelled", "interrupted", "completed"]
        can_cancel = job.status.value in ["pending", "running"]
        
        # Show logs only if job is not pending or cancelled
        show_logs = job.status.value not in ["pending", "cancelled"]
        
        # Update footer bindings dynamically
        self._update_bindings(can_cancel, can_retry)
        
        try:
            # Hide/show cancel button
            cancel_button = self.query_one("#cancel-button", Button)
            cancel_button.display = can_cancel
            
            # Hide/show retry buttons
            retry_inplace = self.query_one("#retry-inplace-button", Button)
            retry_then = self.query_one("#retry-then-button", Button)
            retry_now = self.query_one("#retry-now-button", Button)
            retry_nodeps = self.query_one("#retry-nodeps-button", Button)
            retry_inplace.display = can_retry
            retry_then.display = can_retry
            retry_now.display = can_retry
            retry_nodeps.display = can_retry
            
            # Hide/show log preview sections and full logs button
            self.query_one("#stdout-header", Static).display = show_logs
            self.query_one("#stdout-container", Container).display = show_logs
            self.query_one("#stderr-header", Static).display = show_logs
            self.query_one("#stderr-container", Container).display = show_logs
            self.query_one("#logs-button", Button).display = show_logs
        except Exception:
            pass  # Widgets may not be mounted yet

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
        # Format ETA
        eta_str = (
            format_eta_display(job.eta)
            if hasattr(job, "eta") and job.eta
            else "-"
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
            f"ETA:         {eta_str}\n"
            f"Exit Code:   {exit_code_str}"
        )
        self.query_one("#job-metadata", Static).update(metadata)

        # Update configuration
        cmd_str = ' '.join(job.command)

        config = (
            f"Command:     {cmd_str}\n"
            f"Working Dir: {job.working_dir or 'Default'}\n"
        )
        if job.conda_env:
            config += f"Conda Env:   {job.conda_env}\n"
        config += (
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

    def _update_bindings(self, can_cancel: bool, can_retry: bool):
        """
        Update footer bindings based on job status.

        Args:
            can_cancel: Whether cancel action is available
            can_retry: Whether retry action is available
        """
        # Start with base bindings
        new_bindings = [
            ("escape", "pop_screen", "Back"),
            ("l", "view_logs", "Logs"),
        ]
        
        # Add conditional bindings
        if can_cancel:
            new_bindings.append(self._cancel_binding)
        if can_retry:
            new_bindings.append(self._retry_binding)
        
        # Always add quit at the end
        new_bindings.append(("q", "quit", "Quit"))
        
        # Update the bindings
        self.BINDINGS = new_bindings

    def action_view_logs(self):
        """
        View full job logs (limited to prevent UI freeze).

        Bound to 'l' key.
        """
        if hasattr(self.app, "client"):
            try:
                # Fetch logs with a reasonable limit to prevent UI freeze
                MAX_LINES = 5000
                
                # Fetch stdout logs
                stdout_logs = self.app.client.get_job_logs(
                    self.job_id, lines=MAX_LINES, stderr=False
                )
                
                # Fetch stderr logs
                stderr_logs = self.app.client.get_job_logs(
                    self.job_id, lines=MAX_LINES, stderr=True
                )

                # Process logs to handle escape sequences
                stdout = stdout_logs if stdout_logs else "No stdout logs"
                stderr = stderr_logs if stderr_logs else "No stderr logs"

                # Apply escape sequence processing
                stdout = process_log_escape_sequences(stdout)
                stderr = process_log_escape_sequences(stderr)

                # Count lines to determine if we hit the limit
                stdout_lines = len(stdout.split('\n')) if stdout != "No stdout logs" else 0
                stderr_lines = len(stderr.split('\n')) if stderr != "No stderr logs" else 0

                # Update the STDOUT TextArea widget
                stdout_widget = self.query_one("#stdout-preview", TextArea)
                stdout_widget.load_text(stdout)

                # Update the STDERR TextArea widget
                stderr_widget = self.query_one("#stderr-preview", TextArea)
                stderr_widget.load_text(stderr)

                # Update headers with line limit info
                stdout_header = "Full STDOUT"
                if stdout_lines >= MAX_LINES:
                    stdout_header = f"Full STDOUT (showing last {MAX_LINES} lines)"
                self.query_one("#stdout-header", Static).update(stdout_header)

                stderr_header = "Full STDERR"
                if stderr_lines >= MAX_LINES:
                    stderr_header = f"Full STDERR (showing last {MAX_LINES} lines)"
                self.query_one("#stderr-header", Static).update(stderr_header)
                
            except Exception as e:
                stdout_widget = self.query_one("#stdout-preview", TextArea)
                stdout_widget.load_text(f"Error fetching stdout logs: {e}")
                stderr_widget = self.query_one("#stderr-preview", TextArea)
                stderr_widget.load_text(f"Error fetching stderr logs: {e}")

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

    def action_pop_screen(self):
        """
        Go back to previous screen.

        Bound to 'escape' key.
        """
        self.app.pop_screen()

    def action_show_retry_menu(self):
        """
        Show retry menu/info.

        Bound to 'r' key.
        """
        if self.job_data and self.job_data.status.value in ["failed", "cancelled", "interrupted", "completed"]:
            self.app.notify(
                "Click a retry button below or use the Jobs screen to retry",
                title="Retry Options",
            )
        else:
            self.app.notify(
                "Job cannot be retried (must be failed, cancelled, interrupted, or completed)",
                severity="warning"
            )

    def action_retry_inplace(self):
        """Retry job in-place (same job_id)."""
        if not self._can_retry():
            return

        if hasattr(self.app, "client"):
            try:
                response = self.app.client.session.post(
                    f"{self.app.client.base_url}/jobs/{self.job_id}/retry-inplace",
                    timeout=30
                )
                response.raise_for_status()
                self.app.notify(f"Job {self.job_id} reset to PENDING (in-place)")
                # Refresh job data
                job = self.app.client.get_job(self.job_id)
                self.update_data(job)
            except Exception as e:
                self.app.notify(f"Error retrying job: {e}", severity="error")

    def action_retry_then(self):
        """Retry job from original commit (new job_id)."""
        if not self._can_retry():
            return

        if hasattr(self.app, "client"):
            try:
                new_job = self.app.client.retry_job_then(self.job_id)
                self.app.notify(
                    f"Created new job {new_job.job_id} from original commit",
                    title="Retry Success"
                )
            except Exception as e:
                self.app.notify(f"Error retrying job: {e}", severity="error")

    def action_retry_now(self):
        """Retry job with fresh snapshot (new job_id)."""
        if not self._can_retry():
            return

        if hasattr(self.app, "client"):
            try:
                new_job = self.app.client.retry_job_now(self.job_id)
                self.app.notify(
                    f"Created new job {new_job.job_id} with fresh snapshot",
                    title="Retry Success"
                )
            except Exception as e:
                self.app.notify(f"Error retrying job: {e}", severity="error")

    def action_retry_no_deps(self):
        """Retry job with fresh snapshot without dependencies (new job_id)."""
        if not self._can_retry():
            return

        if hasattr(self.app, "client"):
            try:
                new_job = self.app.client.retry_job_no_deps(self.job_id)
                self.app.notify(
                    f"Created new job {new_job.job_id} with fresh snapshot (no dependencies)",
                    title="Retry Success"
                )
            except Exception as e:
                self.app.notify(f"Error retrying job: {e}", severity="error")

    def _can_retry(self) -> bool:
        """Check if job can be retried."""
        if not self.job_data or self.job_data.status.value not in ["failed", "cancelled", "interrupted", "completed"]:
            self.app.notify(
                "Job cannot be retried (must be failed, cancelled, interrupted, or completed)",
                severity="warning"
            )
            return False
        return True

    def on_button_pressed(self, event):
        """Handle button presses."""
        if event.button.id == "logs-button":
            self.action_view_logs()
        elif event.button.id == "cancel-button":
            self.action_cancel_job()
        elif event.button.id == "back-button":
            self.action_pop_screen()
        elif event.button.id == "retry-inplace-button":
            self.action_retry_inplace()
        elif event.button.id == "retry-then-button":
            self.action_retry_then()
        elif event.button.id == "retry-now-button":
            self.action_retry_now()
        elif event.button.id == "retry-nodeps-button":
            self.action_retry_no_deps()
