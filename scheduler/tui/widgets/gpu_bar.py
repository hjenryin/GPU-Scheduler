
from textual.widgets import ProgressBar


class GPUBar(ProgressBar):
    """Custom progress bar widget for GPU utilization"""

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        **kwargs
    ):
        """
        Initialize GPU bar widget.
        
        Args:
            gpu_id: GPU ID
            utilization: Utilization percentage (0-100)
            memory_used: Used memory in bytes
            memory_total: Total memory in bytes
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.gpu_id = gpu_id
        self.utilization = utilization
        self.memory_used = memory_used
        self.memory_total = memory_total

    def update_stats(
        self,
        utilization: float,
        memory_used: int,
        memory_total: int
    ):
        """
        Update GPU statistics.
        
        Args:
            utilization: New utilization percentage
            memory_used: New used memory
            memory_total: New total memory
        """
        pass

    def render(self) -> str:
        """
        Render the widget (Textual method).
        
        Returns:
            Renderable content for the widget
        """
        pass
