
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
        self._setup_columns()

    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Node, Status, GPUs, Free, Running, Last Heartbeat
        """
        pass

    def update_nodes(self, nodes: List[Node]):
        """
        Update table with node data.
        
        Args:
            nodes: List of Node instances
        """
        pass

    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (node name)
        """
        pass
