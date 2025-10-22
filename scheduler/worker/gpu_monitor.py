from typing import List

from scheduler.core.config import Config
from scheduler.core.exceptions import GPUNotFoundException
from scheduler.core.models import GPUStats


class GPUMonitor:
    """Monitors GPU status and statistics"""

    def __init__(self, config: Config):
        """
        Initialize GPU monitor.
        
        Args:
            config: Configuration instance
        """
        pass

    def detect_gpus(self) -> int:
        """
        Auto-detect number of GPUs on this machine.
        
        Returns:
            Number of GPUs detected
            
        Raises:
            RuntimeError: If nvidia-smi not available or fails
        """
        pass

    def poll_gpu_stats(self) -> List[GPUStats]:
        """
        Poll current GPU statistics.
        
        Returns:
            List of GPUStats for each GPU
            
        Raises:
            RuntimeError: If polling fails
        """
        pass

    def start_monitoring(self):
        """
        Start background GPU monitoring thread.
        """
        pass

    def stop_monitoring(self):
        """
        Stop background GPU monitoring thread.
        """
        pass

    def get_latest_stats(self) -> List[GPUStats]:
        """
        Get most recent GPU statistics.
        
        Returns:
            List of latest GPUStats
        """
        pass
