from typing import Optional
from scheduler.core.config import Config
from scheduler.core.models import Job, GPUMonitor

class HeartbeatSender:
    """Sends periodic heartbeat to head node"""

    def __init__(
        self,
        node_name: str,
        head_address: str,
        gpu_monitor: GPUMonitor,
        config: Config
    ):
        """
        Initialize heartbeat sender.
        
        Args:
            node_name: This node's name
            head_address: Head node address
            gpu_monitor: GPUMonitor instance
            config: Configuration instance
        """
        pass

    def start(self):
        """
        Start heartbeat thread.
        """
        pass

    def stop(self):
        """
        Stop heartbeat thread.
        """
        pass

    def send_heartbeat(self) -> bool:
        """
        Send a single heartbeat to head node.
        
        Returns:
            True if successful, False otherwise
        """
        pass

    def poll_for_job(self) -> Optional[Job]:
        """
        Long-poll head node for job assignment.
        
        Returns:
            Job if assigned, None if no job available
        """
        pass
