from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from scheduler.api.schemas import Node, Job
    
class NodesScreen(Screen):
    """Detailed node information screen"""

    def compose(self) -> ComposeResult:
        """
        Compose the nodes detail layout.
        
        Yields:
            Widgets for node details (node selector, GPU table, job list)
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

    def on_node_selected(self, node_name: str):
        """
        Handle node selection.
        
        Args:
            node_name: Selected node name
        """
        pass
