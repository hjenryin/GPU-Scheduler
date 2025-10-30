from typing import List, Optional
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, Horizontal, Vertical
from scheduler.core import Node, Job  # Import from peer submodule's public API
from scheduler.tui.utils import create_gpu_utilization_bar, format_gpu_memory


class NodesScreen(Screen):
    """Detailed node information screen"""

    BINDINGS = [
        ("c", "switch_to_cluster", "Cluster"),
        ("j", "switch_to_jobs", "Jobs"),
        ("g", "switch_to_gpus", "GPUs"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
        ("escape", "switch_to_cluster", "Back"),
    ]

    def __init__(self):
        super().__init__()
        self.selected_node: Optional[str] = None
        self.nodes_data: List[Node] = []
        self.jobs_data: List[Job] = []
        self.util_threshold: float = 10.0
        self.mem_threshold: float = 10.0
        self.stable_time: int = 30

    def compose(self) -> ComposeResult:
        """
        Compose the nodes detail layout.

        Yields:
            Widgets for node details (node selector, GPU table, job list)
        """
        yield Header()
        yield Container(
            Horizontal(
                Vertical(
                    Static("NODES", id="nodes-list-header"),
                    DataTable(id="nodes-list"),
                ),
                Vertical(
                    Static("", id="node-detail-header"),
                    Static("", id="node-detail-info"),
                    Static("GPUs", id="gpu-detail-header"),
                    DataTable(id="gpu-detail-table"),
                    Static("Running Jobs", id="jobs-detail-header"),
                    Static("", id="jobs-detail-list"),
                ),
                id="nodes-horizontal",
            ),
            id="nodes-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up tables when screen is mounted."""
        # Set up nodes list
        nodes_list = self.query_one("#nodes-list", DataTable)
        nodes_list.add_columns("Node", "Status", "GPUs")
        nodes_list.cursor_type = "row"

        # Set up GPU detail table
        gpu_table = self.query_one("#gpu-detail-table", DataTable)
        gpu_table.add_columns("GPU", "Util", "Memory", "Temp", "Power", "Status", "Job")

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
        # Filter to only active nodes (exclude disconnected)
        from scheduler.core import NodeStatus
        active_nodes = [n for n in nodes if n.status != NodeStatus.DISCONNECTED]

        self.nodes_data = active_nodes
        self.jobs_data = jobs
        self.util_threshold = util_threshold
        self.mem_threshold = mem_threshold
        self.stable_time = stable_time

        # Update nodes list
        nodes_list = self.query_one("#nodes-list", DataTable)
        # Preserve cursor position
        try:
            old_cursor = nodes_list.cursor_row if nodes_list.row_count > 0 else 0
        except (TypeError, AttributeError):
            old_cursor = 0
        nodes_list.clear()
        for node in active_nodes:
            nodes_list.add_row(
                node.node_name, node.status.value.capitalize(), f"{node.num_gpus} GPUs"
            )
        # Restore cursor position if table has rows
        try:
            if nodes_list.row_count > 0:
                nodes_list.move_cursor(row=min(old_cursor, nodes_list.row_count - 1))
        except (TypeError, AttributeError):
            pass

        # If a node was selected, update its details
        if self.selected_node:
            self._update_node_details(self.selected_node)
        elif nodes:
            # Select first node by default
            self.on_node_selected(nodes[0].node_name)

    def on_data_table_row_selected(self, event):
        """Handle row selection in nodes list."""
        if event.data_table.id == "nodes-list":
            row_key = event.row_key
            table = event.data_table
            row_data = table.get_row(row_key)
            node_name = str(row_data[0])
            self.on_node_selected(node_name)

    def on_node_selected(self, node_name: str):
        """
        Handle node selection.

        Args:
            node_name: Selected node name
        """
        self.selected_node = node_name
        self._update_node_details(node_name)

    def _update_node_details(self, node_name: str):
        """Update the detail panel for a specific node."""
        # Find the node
        node = next((n for n in self.nodes_data if n.node_name == node_name), None)
        if not node:
            return

        # Update header
        self.query_one("#node-detail-header", Static).update(f"Node: {node_name}")

        # Update node info
        # Use proper free GPU calculation based on thresholds and stability
        free_gpu_ids = node.get_free_gpus(
            self.util_threshold, self.mem_threshold, self.stable_time
        )
        free_gpu_count = len(free_gpu_ids)
        info_text = (
            f"Status: {node.status.value.capitalize()}\n"
            f"Address: {node.address if hasattr(node, 'address') else 'N/A'}\n"
            f"GPUs: {node.num_gpus} total, {free_gpu_count} free, "
            f"{node.num_gpus - free_gpu_count} in use"
        )
        self.query_one("#node-detail-info", Static).update(info_text)

        # Update GPU table
        gpu_table = self.query_one("#gpu-detail-table", DataTable)
        # Preserve cursor position
        try:
            old_cursor_gpu = gpu_table.cursor_row if gpu_table.row_count > 0 else 0
        except (TypeError, AttributeError):
            old_cursor_gpu = 0
        gpu_table.clear()
        for gpu in node.gpus:
            # Use same logic as GPU screen for consistency
            is_free = gpu.stats.is_free(self.util_threshold, self.mem_threshold)
            is_stable = gpu.is_stable(self.stable_time)

            if is_free and is_stable:
                status = "Free"
                job_id = "-"
            elif gpu.stats.running_job_id is not None:
                status = "In Use"
                job_id = gpu.stats.running_job_id
            else:
                # GPU has no job but is not yet stable or above thresholds
                status = "Waiting"
                job_id = "-"

            gpu_table.add_row(
                str(gpu.gpu_id),
                create_gpu_utilization_bar(gpu.stats.utilization, width=10),
                f"{format_gpu_memory(gpu.stats.memory_used)}/{format_gpu_memory(gpu.stats.memory_total)}",
                f"{gpu.stats.temperature}°C" if gpu.stats.temperature else "N/A",
                f"{gpu.stats.power_draw}W" if gpu.stats.power_draw else "N/A",
                status,
                job_id,
            )
        # Restore cursor position if table has rows
        try:
            if gpu_table.row_count > 0:
                gpu_table.move_cursor(row=min(old_cursor_gpu, gpu_table.row_count - 1))
        except (TypeError, AttributeError):
            pass

        # Update running jobs
        running_jobs = [
            j
            for j in self.jobs_data
            if j.assigned_node == node_name and j.status.value == "running"
        ]
        jobs_text = ""
        for job in running_jobs:
            gpu_ids = job.assigned_gpus if hasattr(job, "assigned_gpus") else []
            gpu_str = ",".join(map(str, gpu_ids)) if gpu_ids else "?"
            jobs_text += f"  • {job.job_id}: {job.name or 'N/A'} (GPUs: {gpu_str})\n"
        if not jobs_text:
            jobs_text = "  No running jobs"
        self.query_one("#jobs-detail-list", Static).update(jobs_text)
