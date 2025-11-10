from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from textual.widgets import Header, Footer, Static, DataTable
from textual.containers import Container, VerticalScroll
from scheduler.core import Node  # Import from peer submodule's public API
from scheduler.tui.utils import create_gpu_utilization_bar, format_gpu_memory


class GPUsScreen(Screen):
    """GPU details screen showing all GPUs across all nodes"""

    BINDINGS = [
        ("c", "switch_to_cluster", "Cluster"),
        ("n", "switch_to_nodes", "Nodes"),
        ("j", "switch_to_jobs", "Jobs"),
        ("q", "quit", "Quit"),
        ("h", "help", "Help"),
        ("escape", "switch_to_cluster", "Back"),
    ]

    def compose(self) -> ComposeResult:
        """
        Compose the GPU details layout.

        Yields:
            Widgets for GPU details (GPU grid, stats tables)
        """
        yield Header()
        yield Container(
            VerticalScroll(
                Static("GPU OVERVIEW", id="gpu-overview-header"),
                Static("", id="gpu-summary"),
                Static("ALL GPUs", id="all-gpus-header"),
                DataTable(id="gpus-table"),
                id="gpus-scroll"
            ),
            id="gpus-container",
        )
        yield Footer()

    def on_mount(self):
        """Set up table when screen is mounted."""
        gpu_table = self.query_one("#gpus-table", DataTable)
        gpu_table.add_columns(
            "Node", "GPU", "Utilization", "Memory", "Temp", "Power", "Status", "Job"
        )
        gpu_table.cursor_type = "row"

    def update_data(
        self,
        nodes: List[Node],
        util_threshold: float = 10.0,
        mem_threshold: float = 10.0,
        stable_time: int = 30,
    ):
        """
        Update screen with new data.

        Args:
            nodes: List of Node instances
            util_threshold: GPU utilization threshold
            mem_threshold: GPU memory threshold
            stable_time: Required stable time in seconds
        """
        # Filter to only active nodes (exclude disconnected)
        from scheduler.core import NodeStatus
        active_nodes = [n for n in nodes if n.status != NodeStatus.DISCONNECTED]

        # Calculate summary statistics (only for active nodes)
        total_gpus = sum(node.num_gpus for node in active_nodes)
        free_gpus = sum(
            len(node.get_free_gpus(util_threshold, mem_threshold, stable_time))
            for node in active_nodes
        )
        # Count frozen GPUs
        frozen_gpus = sum(
            sum(1 for gpu in node.gpus if gpu.is_frozen())
            for node in active_nodes
        )
        in_use_gpus = total_gpus - free_gpus - frozen_gpus

        # Calculate average utilization (only for active nodes)
        all_utils = []
        for node in active_nodes:
            for gpu in node.gpus:
                all_utils.append(gpu.stats.utilization)
        avg_util = sum(all_utils) / len(all_utils) if all_utils else 0

        # Calculate total memory (only for active nodes)
        total_memory = 0
        used_memory = 0
        for node in active_nodes:
            for gpu in node.gpus:
                total_memory += gpu.stats.memory_total
                used_memory += gpu.stats.memory_used

        summary = (
            f"Total GPUs: {total_gpus} | Free: {free_gpus} | "
            f"In Use: {in_use_gpus} | Frozen: {frozen_gpus} | "
            f"Avg Utilization: {avg_util:.1f}%\n"
            f"Memory: {format_gpu_memory(used_memory)} / "
            f"{format_gpu_memory(total_memory)} "
            f"({100 * used_memory / total_memory if total_memory > 0 else 0:.1f}%)"
        )
        self.query_one("#gpu-summary", Static).update(summary)

        # Update GPU table (only for active nodes)
        gpu_table = self.query_one("#gpus-table", DataTable)
        # Preserve cursor position
        try:
            old_cursor = gpu_table.cursor_row if gpu_table.row_count > 0 else 0
        except (TypeError, AttributeError):
            old_cursor = 0
        gpu_table.clear()

        for node in active_nodes:
            for gpu in node.gpus:
                # Check if GPU is frozen first
                if gpu.is_frozen():
                    status = "Frozen"
                    job_id = "-"
                else:
                    # Check if GPU is free using the same logic as get_free_gpus
                    # A GPU is only truly "Free" if it meets utilization/memory
                    # thresholds AND is stable
                    is_free = gpu.stats.is_free(util_threshold, mem_threshold)
                    is_stable = gpu.is_stable(stable_time)

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
                    node.node_name,
                    f"GPU {gpu.gpu_id}",
                    create_gpu_utilization_bar(gpu.stats.utilization, width=15),
                    f"{format_gpu_memory(gpu.stats.memory_used)}/{format_gpu_memory(gpu.stats.memory_total)}",
                    f"{gpu.stats.temperature}°C" if gpu.stats.temperature else "N/A",
                    f"{gpu.stats.power_draw}W" if gpu.stats.power_draw else "N/A",
                    status,
                    job_id,
                )
        # Restore cursor position if table has rows
        try:
            if gpu_table.row_count > 0:
                gpu_table.move_cursor(row=min(old_cursor, gpu_table.row_count - 1))
        except (TypeError, AttributeError):
            pass
