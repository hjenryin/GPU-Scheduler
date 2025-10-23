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
        ("n", "switch_to_cluster", "Cluster"),
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
                id="nodes-horizontal"
            ),
            id="nodes-container"
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
        gpu_table.add_columns("GPU", "Util", "Memory", "Temp", "Power", "Job")

    def update_data(self, nodes: List[Node], jobs: List[Job]):
        """
        Update screen with new data.

        Args:
            nodes: List of Node instances
            jobs: List of Job instances
        """
        self.nodes_data = nodes
        self.jobs_data = jobs

        # Update nodes list
        nodes_list = self.query_one("#nodes-list", DataTable)
        nodes_list.clear()
        for node in nodes:
            nodes_list.add_row(
                node.node_name,
                node.status,
                f"{node.num_gpus} GPUs"
            )

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
        free_gpu_count = len([gpu for gpu in node.gpus if gpu.available])
        info_text = (
            f"Status: {node.status}\n"
            f"Address: {node.address if hasattr(node, 'address') else 'N/A'}\n"
            f"GPUs: {node.num_gpus} total, {free_gpu_count} free, {node.num_gpus - free_gpu_count} in use"
        )
        self.query_one("#node-detail-info", Static).update(info_text)

        # Update GPU table
        gpu_table = self.query_one("#gpu-detail-table", DataTable)
        gpu_table.clear()
        for gpu in node.gpus:
            job_id = "free" if gpu.available else (gpu.assigned_job_id or "-")
            gpu_table.add_row(
                str(gpu.gpu_id),
                create_gpu_utilization_bar(gpu.utilization, width=10),
                f"{format_gpu_memory(gpu.memory_used)}/{format_gpu_memory(gpu.memory_total)}",
                f"{gpu.temperature}°C" if gpu.temperature else "N/A",
                f"{gpu.power_draw}W" if gpu.power_draw else "N/A",
                job_id
            )

        # Update running jobs
        running_jobs = [j for j in self.jobs_data if j.assigned_node == node_name and j.status.value == "running"]
        jobs_text = ""
        for job in running_jobs:
            gpu_ids = job.assigned_gpus if hasattr(job, 'assigned_gpus') else []
            gpu_str = ",".join(map(str, gpu_ids)) if gpu_ids else "?"
            jobs_text += f"  • {job.job_id}: {job.name or 'N/A'} (GPUs: {gpu_str})\n"
        if not jobs_text:
            jobs_text = "  No running jobs"
        self.query_one("#jobs-detail-list", Static).update(jobs_text)
