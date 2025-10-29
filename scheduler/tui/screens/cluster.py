from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, VerticalScroll
from typing import List
import logging
from scheduler.core import Node, Job, NodeStatus
from scheduler.tui.utils import (
    create_gpu_utilization_bar,
    format_runtime,
    format_time_ago,
)

logger = logging.getLogger(__name__)


class ClusterScreen(Screen):
    """Cluster overview screen showing summary of nodes, GPUs, and jobs"""

    BINDINGS = [
        ("n", "switch_to_nodes", "Nodes"),
        ("j", "switch_to_jobs", "Jobs"),
        ("g", "switch_to_gpus", "GPUs"),
        ("escape", "switch_to_cluster", "Overview"),
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
            id="cluster-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up tables when screen is mounted."""
        # Set up node table
        node_table = self.query_one("#node-table", DataTable)
        node_table.add_columns(
            "Node", "Status", "GPUs", "Free", "Running", "Last Heartbeat"
        )
        node_table.cursor_type = "row"

        # Set up job table
        job_table = self.query_one("#job-table", DataTable)
        job_table.add_columns("Job ID", "Name", "Status", "Node", "GPUs", "Runtime")
        job_table.cursor_type = "row"

    def update_data(
        self,
        nodes: List[Node],
        jobs: List[Job],
        util_threshold: float = 10.0,
        mem_threshold: float = 10.0,
        stable_time: int = 30,
    ):
        """
        Update screen with new data.

        Args:
            nodes: List of Node instances
            jobs: List of Job instances
            util_threshold: GPU utilization threshold
            mem_threshold: GPU memory threshold
            stable_time: Required stable time in seconds
        """
        logger.info(
            f"ClusterScreen.update_data called with {len(nodes)} nodes "
            f"and {len(jobs)} jobs"
        )

        # Update summary - filter out disconnected nodes (show connected + initializing)
        active_nodes_list = [
            n for n in nodes if n.status != NodeStatus.DISCONNECTED
        ]
        active_nodes = len(active_nodes_list)

        total_gpus = sum(node.num_gpus for node in active_nodes_list)
        # Use the proper get_free_gpus method like the scheduler does
        free_gpus = sum(
            len(node.get_free_gpus(util_threshold, mem_threshold, stable_time))
            for node in active_nodes_list
        )
        in_use_gpus = total_gpus - free_gpus

        pending_jobs = len([j for j in jobs if j.status.value == "pending"])
        running_jobs = len([j for j in jobs if j.status.value == "running"])
        completed_jobs = len([j for j in jobs if j.status.value == "completed"])
        failed_jobs = len([j for j in jobs if j.status.value == "failed"])

        summary = (
            f"Nodes: {active_nodes} active | "
            f"GPUs: {total_gpus} total, {free_gpus} free, "
            f"{in_use_gpus} in use\n"
            f"Jobs: {pending_jobs} pending, {running_jobs} running, "
            f"{completed_jobs} completed, {failed_jobs} failed"
        )
        logger.info(f"Summary: {summary}")
        self.query_one("#cluster-summary", Static).update(summary)

        # Update node table - show active nodes (exclude disconnected)
        node_table = self.query_one("#node-table", DataTable)
        node_table.clear()
        for node in active_nodes_list:
            free_gpu_count = len(
                node.get_free_gpus(util_threshold, mem_threshold, stable_time)
            )
            running_job_count = len(
                [
                    j
                    for j in jobs
                    if j.assigned_node == node.node_name and j.status.value == "running"
                ]
            )
            node_table.add_row(
                node.node_name,
                node.status.value.capitalize(),
                str(node.num_gpus),
                str(free_gpu_count),
                f"{running_job_count} jobs",
                format_time_ago(node.last_heartbeat),
            )

        # Update GPU bars - show active nodes (exclude disconnected)
        gpu_bars_text = ""
        for node in active_nodes_list:
            logger.info(f"Node {node.node_name}: {len(node.gpus)} GPUs")
            gpu_line = f"{node.node_name}: "
            for gpu in node.gpus[:4]:  # Show first 4 GPUs
                bar = create_gpu_utilization_bar(gpu.stats.utilization, width=10)
                gpu_line += f"GPU{gpu.gpu_id} {bar}  "
                logger.debug(f"  GPU{gpu.gpu_id}: util={gpu.stats.utilization}%")
            if len(node.gpus) > 4:
                gpu_line += "..."
            gpu_bars_text += gpu_line + "\n"
        logger.info(f"GPU bars text length: {len(gpu_bars_text)}")
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
                str(job.requirements) if job.requirements else "?",
                format_runtime(job.runtime) if hasattr(job, "runtime") else "-",
            )
