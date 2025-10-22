
from textual.screen import Screen
from textual.app import ComposeResult
from typing import List
from scheduler.api.schemas import Node, Job

class ClusterScreen(Screen):
    """Cluster overview screen showing summary of nodes, GPUs, and jobs"""

    def compose(self) -> ComposeResult:
        """
        Compose the cluster overview layout.
        
        Yields:
            Widgets for cluster overview (stats, node table, GPU bars, job list)
        """
        pass

    def update_data(self, nodes: List[Node], jobs: List[Job]):
        """
        Update screen with new data.
        
        Args:
            nodes: List of Node instances
            jobs: List of Job instances
        """
        pass
