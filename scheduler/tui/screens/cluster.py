from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, VerticalScroll
from typing import List
from scheduler.api.schemas import Node, Job
from scheduler.tui.utils import get_status_color, create_gpu_utilization_bar, format_runtime


class ClusterScreen(Screen):
    """Cluster overview screen showing summary of nodes, GPUs, and jobs"""

    BINDINGS = [
        ("n", "switch_to_nodes", "Nodes"),
        ("j", "switch_to_jobs", "Jobs"),
        ("g", "switch_to_gpus", "GPUs"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
        ("r", "refresh", "Refresh"),
    ]

    def compose(self) -> ComposeResult:
        """
        Compose the cluster overview layout.

        Yields:
            Widgets for cluster overview (stats, node table, GPU bars, job list)
        """
        yield Header()
        yield Container(
            Static("", id="cluster-summary"),
            Static("NODE STATUS", id="node-header"),
            DataTable(id="node-table"),
            Static("GPU UTILIZATION", id="gpu-header"),
            VerticalScroll(Static("", id="gpu-bars"), id="gpu-scroll"),
            Static("ACTIVE JOBS", id="job-header"),
            DataTable(id="job-table"),
            id="cluster-container"
        )
        yield Footer()

    def on_mount(self):
        """Set up tables when screen is mounted."""
        # Set up node table
        node_table = self.query_one("#node-table", DataTable)
        node_table.add_columns("Node", "Status", "GPUs", "Free", "Running", "Last Heartbeat")
        node_table.cursor_type = "row"

        # Set up job table
        job_table = self.query_one("#job-table", DataTable)
        job_table.add_columns("Job ID", "Name", "Status", "Node", "GPUs", "Runtime")
        job_table.cursor_type = "row"

    def update_data(self, nodes: List[Node], jobs: List[Job]):
        """
        Update screen with new data.

        Args:
            nodes: List of Node instances
            jobs: List of Job instances
        """
        # Update summary
        total_gpus = sum(node.num_gpus for node in nodes)
        free_gpus = sum(len([gpu for gpu in node.gpus if gpu.available]) for node in nodes)
        in_use_gpus = total_gpus - free_gpus

        connected_nodes = len([n for n in nodes if n.status == "connected"])
        disconnected_nodes = len([n for n in nodes if n.status == "disconnected"])

        pending_jobs = len([j for j in jobs if j.status.value == "pending"])
        running_jobs = len([j for j in jobs if j.status.value == "running"])
        completed_jobs = len([j for j in jobs if j.status.value == "completed"])
        failed_jobs = len([j for j in jobs if j.status.value == "failed"])

        summary = (
            f"Nodes: {connected_nodes} connected, {disconnected_nodes} disconnected | "
            f"GPUs: {total_gpus} total, {free_gpus} free, {in_use_gpus} in use\n"
            f"Jobs: {pending_jobs} pending, {running_jobs} running, {completed_jobs} completed, {failed_jobs} failed"
        )
        self.query_one("#cluster-summary", Static).update(summary)

        # Update node table
        node_table = self.query_one("#node-table", DataTable)
        node_table.clear()
        for node in nodes:
            free_gpu_count = len([gpu for gpu in node.gpus if gpu.available])
            running_job_count = len([j for j in jobs if j.assigned_node == node.node_name and j.status.value == "running"])
            node_table.add_row(
                node.node_name,
                node.status,
                str(node.num_gpus),
                str(free_gpu_count),
                f"{running_job_count} jobs",
                "N/A"  # TODO: Calculate time since last heartbeat
            )

        # Update GPU bars
        gpu_bars_text = ""
        for node in nodes:
            gpu_line = f"{node.node_name}: "
            for gpu in node.gpus[:4]:  # Show first 4 GPUs
                bar = create_gpu_utilization_bar(gpu.utilization, width=10)
                gpu_line += f"GPU{gpu.gpu_id} {bar}  "
            if len(node.gpus) > 4:
                gpu_line += "..."
            gpu_bars_text += gpu_line + "\n"
        self.query_one("#gpu-bars", Static).update(gpu_bars_text)

        # Update job table (show active jobs)
        job_table = self.query_one("#job-table", DataTable)
        job_table.clear()
        active_jobs = [j for j in jobs if j.status.value in ["pending", "running"]][:10]
        for job in active_jobs:
            job_table.add_row(
                job.job_id,
                job.name or "N/A",
                job.status.value,
                job.assigned_node or "-",
                str(job.requirements.num_gpus) if job.requirements else "?",
                format_runtime(job.runtime) if hasattr(job, 'runtime') else "-"
            )
