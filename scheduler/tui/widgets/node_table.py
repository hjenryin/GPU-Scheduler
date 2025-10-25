
from textual.widgets import DataTable
from typing import List, Optional
from scheduler.core import Job, JobStatus, Node



class NodeTable(DataTable):
    """Custom DataTable for displaying node information"""

    def __init__(self, **kwargs):
        """
        Initialize node table widget.
        
        Args:
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self._columns_setup = False

    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Node, Status, GPUs, Free, Running, Last Heartbeat
        """
        if not self._columns_setup:
            self.add_columns("Node", "Status", "GPUs", "Free", "Running", "Last Heartbeat")
            self.cursor_type = "row"
            self._columns_setup = True

    def update_nodes(self, nodes: List[Node]):
        """
        Update table with node data.
        
        Args:
            nodes: List of Node instances
        """
        # Ensure columns are set up
        self._setup_columns()
        
        self.clear()
        for node in nodes:
            free_gpu_count = len([gpu for gpu in node.gpus if gpu.available])
            running_job_count = len([j for j in getattr(self, 'jobs_data', []) if j.assigned_node == node.node_name and j.status.value == "running"])
            self.add_row(
                node.node_name,
                node.status,
                str(node.num_gpus),
                str(free_gpu_count),
                f"{running_job_count} jobs",
                "N/A"  # TODO: Calculate time since last heartbeat
            )

    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (node name)
        """
        # Emit a custom event that can be handled by parent components
        self.post_message(self.NodeSelected(row_key))
    
    class NodeSelected:
        """Event emitted when a node is selected."""
        def __init__(self, node_name: str):
            self.node_name = node_name
