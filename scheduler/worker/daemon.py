from scheduler.core.config import Config
from typing import Optional

class WorkerDaemon:
    """Main worker node daemon"""

    def __init__(self, config: Config, node_name: str, num_gpus: Optional[int] = None):
        """
        Initialize worker daemon.
        
        Args:
            config: Configuration instance
            node_name: Unique node name
            num_gpus: Number of GPUs (auto-detect if None)
        """
        pass

    def start(self):
        """
        Start the worker daemon and all components.
        
        Raises:
            ConnectionException: If cannot connect to head node
        """
        pass

    def stop(self, graceful: bool = True):
        """
        Stop the worker daemon and all components.
        
        Args:
            graceful: If True, wait for jobs to complete
        """
        pass

    def run(self):
        """
        Run the worker daemon main loop (blocking).
        """
        pass

    def register_with_head(self):
        """
        Register this worker with the head node.
        
        Raises:
            ConnectionException: If cannot connect to head node
        """
        pass
