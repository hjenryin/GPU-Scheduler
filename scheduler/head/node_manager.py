from typing import List, Optional

from scheduler.core.config import Config
from scheduler.core.models import GPU, Job, Node
from scheduler.storage.backend import StorageBackend
from scheduler.head import PersistenceManager
from scheduler.core.models import GPUStats

class NodeManager:
    """Manages worker node registry"""

    def __init__(self, persistence: 'PersistenceManager', config: Config):
        """
        Initialize node manager.
        
        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        pass

    def register_node(
        self,
        node_name: str,
        address: str,
        num_gpus: int
    ) -> Node:
        """
        Register a new worker node.
        
        Args:
            node_name: Unique node name
            address: Node address
            num_gpus: Number of GPUs on node
            
        Returns:
            Created Node instance
            
        Raises:
            ValidationException: If node already exists
        """
        pass

    def update_heartbeat(
        self,
        node_name: str,
        gpu_stats: List[GPUStats]
    ):
        """
        Update node heartbeat and GPU statistics.
        
        Args:
            node_name: Node name
            gpu_stats: List of GPU statistics
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass

    def get_node(self, node_name: str) -> Optional[Node]:
        """
        Get node by name.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance if found, None otherwise
        """
        pass

    def list_nodes(self) -> List[Node]:
        """
        List all nodes.
        
        Returns:
            List of Node instances
        """
        pass

    def get_connected_nodes(self) -> List[Node]:
        """
        Get all connected nodes.
        
        Returns:
            List of connected Node instances
        """
        pass

    def check_timeouts(self):
        """
        Check for node heartbeat timeouts and mark as disconnected.
        """
        pass

    def start_node_grace_period(self, node_name: str):
        """
        Start grace period for a node.
        
        Args:
            node_name: Node name
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass

    def assign_gpus_to_job(
        self,
        node_name: str,
        gpu_ids: List[int],
        job_id: str
    ):
        """
        Assign GPUs to a job.
        
        Args:
            node_name: Node name
            gpu_ids: GPU IDs to assign
            job_id: Job ID
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass

    def release_gpus_from_job(
        self,
        node_name: str,
        gpu_ids: List[int]
    ):
        """
        Release GPUs from a job.
        
        Args:
            node_name: Node name
            gpu_ids: GPU IDs to release
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass
