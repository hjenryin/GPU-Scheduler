"""Status screen showing warnings and errors from head and worker."""

from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, VerticalScroll
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class StatusScreen(Screen):
    """Status screen showing warnings and errors from head and local worker"""

    BINDINGS = [
        ("c", "switch_to_cluster", "Cluster"),
        ("n", "switch_to_nodes", "Nodes"),
        ("j", "switch_to_jobs", "Jobs"),
        ("g", "switch_to_gpus", "GPUs"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """
        Compose the status layout.

        Yields:
            Widgets for status view (log tables for head and worker)
        """
        yield Header()
        yield Container(
            VerticalScroll(
                Static("STATUS SUMMARY", id="status-summary-header"),
                Static("", id="status-summary"),
                Static("HEAD NODE LOGS", id="head-logs-header"),
                DataTable(id="head-logs-table"),
                Static("WORKER NODE LOGS", id="worker-logs-header"),
                DataTable(id="worker-logs-table"),
                id="status-scroll"
            ),
            id="status-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up tables when screen is mounted."""
        # Set up head logs table
        head_table = self.query_one("#head-logs-table", DataTable)
        head_table.add_columns(
            "Level", "Count", "Time", "Logger", "Message"
        )
        head_table.cursor_type = "row"

        # Set up worker logs table
        worker_table = self.query_one("#worker-logs-table", DataTable)
        worker_table.add_columns(
            "Level", "Count", "Time", "Logger", "Message"
        )
        worker_table.cursor_type = "row"

    def update_data(self, client):
        """
        Update screen with new log data.

        Args:
            client: SchedulerClient instance
        """
        try:
            # Get head logs
            head_data = client.get_head_logs(limit=50)
            head_logs = head_data.get("logs", [])
            head_stats = head_data.get("stats", {})

            # Get worker logs (from log file if worker is running locally)
            worker_logs = []
            worker_stats = {}
            worker_running = False
            
            try:
                from scheduler.core import is_daemon_running, parse_log_file, get_worker_log_paths, load_config
                import socket
                
                # Check if worker is running locally
                config = load_config()
                node_name = socket.gethostname()
                lockfile_path = os.path.expanduser(f"~/.scheduler/worker-{node_name}.lock")
                
                if is_daemon_running(lockfile_path):
                    worker_running = True
                    # Get worker log paths
                    worker_log_paths = get_worker_log_paths(config)
                    
                    if worker_log_paths:
                        # Process all available log files
                        all_worker_logs = []
                        worker_stats = {"WARNING": 0, "ERROR": 0}
                        
                        for log_path in worker_log_paths:
                            if os.path.exists(log_path):
                                log_entries, log_stats = parse_log_file(log_path, limit=None)
                                all_worker_logs.extend(log_entries)
                                
                                # Update stats with log stats
                                for level_key, count in log_stats.items():
                                    if level_key in worker_stats:
                                        worker_stats[level_key] += count
                        
                        # Sort all logs by timestamp (most recent first)
                        all_worker_logs = sorted(
                            all_worker_logs,
                            key=lambda x: x['timestamp'],
                            reverse=True
                        )
                        
                        # Apply limit
                        worker_logs = all_worker_logs[:50]
                    else:
                        logger.debug("Worker log files not found")
                        worker_logs = []
                        worker_stats = {"WARNING": 0, "ERROR": 0}
                else:
                    logger.debug("Worker daemon not running locally")
                    worker_logs = []
                    worker_stats = {"WARNING": 0, "ERROR": 0}
                    
            except Exception as e:
                logger.debug(f"Could not get worker logs: {e}")
                worker_logs = []
                worker_stats = {"WARNING": 0, "ERROR": 0}

            # Update summary
            summary_text = self._format_summary(head_stats, worker_stats, worker_running)
            summary_widget = self.query_one("#status-summary", Static)
            summary_widget.update(summary_text)

            # Update head logs table
            self._update_logs_table("#head-logs-table", head_logs)

            # Update worker logs table
            self._update_logs_table("#worker-logs-table", worker_logs)

        except Exception as e:
            logger.error(f"Error updating status data: {e}", exc_info=True)
            summary_widget = self.query_one("#status-summary", Static)
            summary_widget.update(f"Error loading status: {e}")

    def _format_summary(self, head_stats: dict, worker_stats: dict, worker_running: bool = False) -> str:
        """Format summary statistics."""
        head_warnings = head_stats.get("WARNING", 0)
        head_errors = head_stats.get("ERROR", 0)
        worker_warnings = worker_stats.get("WARNING", 0)
        worker_errors = worker_stats.get("ERROR", 0)

        summary = []
        summary.append(f"Head:   {head_warnings} warnings, {head_errors} errors")
        
        if worker_running:
            if worker_stats:
                summary.append(f"Worker: {worker_warnings} warnings, {worker_errors} errors")
            else:
                summary.append("Worker: Running locally (no logs yet)")
        else:
            summary.append("Worker: Not running locally")

        return "\n".join(summary)

    def _update_logs_table(self, table_id: str, logs: list):
        """Update a logs table with new data."""
        try:
            table = self.query_one(table_id, DataTable)
            table.clear()

            for log_entry in logs:
                level = log_entry.get("level", "")
                count = log_entry.get("count", 1)
                timestamp_str = log_entry.get("timestamp", "")
                logger_name = log_entry.get("logger_name", "")
                message = log_entry.get("message", "")

                # Format timestamp
                try:
                    timestamp = datetime.fromisoformat(timestamp_str)
                    time_str = timestamp.strftime("%H:%M:%S")
                except Exception:
                    time_str = timestamp_str

                # Truncate logger name for display
                if len(logger_name) > 25:
                    logger_name = "..." + logger_name[-22:]

                # Truncate message for display
                if len(message) > 80:
                    message = message[:77] + "..."

                # Add row with level styling
                level_display = f"[bold {'yellow' if level == 'WARNING' else 'red'}]{level}[/]"
                count_display = f"[bold]×{count}[/]" if count > 1 else ""
                
                table.add_row(
                    level_display,
                    count_display,
                    time_str,
                    logger_name,
                    message
                )

        except Exception as e:
            logger.error(f"Error updating logs table {table_id}: {e}", exc_info=True)

    def action_switch_to_cluster(self):
        """Switch to cluster view."""
        self.app.switch_screen("cluster")

    def action_switch_to_nodes(self):
        """Switch to nodes view."""
        self.app.switch_screen("nodes")

    def action_switch_to_jobs(self):
        """Switch to jobs view."""
        self.app.switch_screen("jobs")

    def action_switch_to_gpus(self):
        """Switch to GPUs view."""
        self.app.switch_screen("gpus")
