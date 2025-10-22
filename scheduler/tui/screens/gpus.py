from typing import List
from textual.screen import Screen
from textual.app import ComposeResult
from scheduler.api.schemas import Node
class GPUsScreen(Screen):
    """GPU details screen showing all GPUs across all nodes"""

    def compose(self) -> ComposeResult:
        """
        Compose the GPU details layout.
        
        Yields:
            Widgets for GPU details (GPU grid, stats tables)
        """
        pass

    def update_data(self, nodes: List[Node]):
        """
        Update screen with new data.
        
        Args:
            nodes: List of Node instances
        """
        pass
