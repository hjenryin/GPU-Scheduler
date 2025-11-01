from typing import List, Optional, Dict
import logging
from datetime import datetime, timedelta

from scheduler.core import Config
from scheduler.core import GPU, Node, GPUStats, NodeStatus
from scheduler.core import NodeNotFoundException, ValidationException
from scheduler.manager.persistence import PersistenceManager

logger = logging.getLogger(__name__)


class NodeManager:
    """Manages worker node registry"""

    def __init__(self, persistence: PersistenceManager, config: Config):
        """
        Initialize node manager.

        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        self.persistence = persistence
        self.config = config
        self.nodes: Dict[str, Node] = {}

        # Load existing nodes from storage
        self._load_nodes()

    def _load_nodes(self):
        """Load nodes from storage into memory"""
        nodes = self.persistence.load_all_nodes()
        for node in nodes:
            self.nodes[node.node_name] = node
        logger.info(f"Loaded {len(nodes)} nodes from storage")

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
        # Check if node already exists
        if node_name in self.nodes:
            # Update existing node
            node = self.nodes[node_name]
            node.address = address
            node.num_gpus = num_gpus
            node.status = NodeStatus.CONNECTED
            logger.info(f"Node {node_name} re-registered")
        else:
            # Create new node with empty GPU list (will be populated on first heartbeat)
            node = Node(
                node_name=node_name,
                address=address,
                num_gpus=num_gpus,
                gpus=[],
                status=NodeStatus.INITIALIZING,
                registered_at=datetime.now()
            )
            self.nodes[node_name] = node
            logger.info(f"Node {node_name} registered with {num_gpus} GPUs")

        self.persistence.save_node(node)
        return node

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
        node = self.nodes.get(node_name)
        if not node:
            raise NodeNotFoundException(f"Node {node_name} not found")

        # Initialize GPUs if this is the first heartbeat
        if not node.gpus:
            node.gpus = []
            for stats in gpu_stats:
                gpu = GPU(
                    gpu_id=stats.gpu_id,
                    stats=stats,
                    stable_since=None
                )
                # Call update_stats to initialize stable_since if GPU is free
                gpu.update_stats(
                    stats,
                    self.config.worker.gpu_util_threshold,
                    self.config.worker.gpu_mem_threshold
                )
                node.gpus.append(gpu)
        else:
            # Update existing GPU stats
            for stats in gpu_stats:
                if stats.gpu_id < len(node.gpus):
                    node.gpus[stats.gpu_id].update_stats(
                        stats,
                        self.config.worker.gpu_util_threshold,
                        self.config.worker.gpu_mem_threshold
                    )

        # Update heartbeat timestamp
        node.update_heartbeat(gpu_stats)

        self.persistence.save_node(node)
        logger.debug(f"Heartbeat received from {node_name}")

    def get_node(self, node_name: str) -> Optional[Node]:
        """
        Get node by name.

        Args:
            node_name: Node name

        Returns:
            Node instance if found, None otherwise
        """
        return self.nodes.get(node_name)

    def list_nodes(self) -> List[Node]:
        """
        List all nodes.

        Returns:
            List of Node instances
        """
        return list(self.nodes.values())

    def get_connected_nodes(self) -> List[Node]:
        """
        Get all connected nodes.

        Returns:
            List of connected Node instances
        """
        connected = [n for n in self.nodes.values() if n.status == NodeStatus.CONNECTED]
        logger.debug(f"Found {len(connected)} connected nodes out of {len(self.nodes)} total nodes")
        for node in connected:
            logger.debug(f"Connected node: {node.node_name}, status: {node.status}, last_heartbeat: {node.last_heartbeat}")
        return connected

    def check_timeouts(self):
        """
        Check for node heartbeat timeouts and mark as disconnected.
        """
        now = datetime.now()
        timeout = timedelta(seconds=self.config.head.heartbeat_timeout)

        for node in self.nodes.values():
            if node.status == NodeStatus.CONNECTED:
                if node.last_heartbeat and (now - node.last_heartbeat) > timeout:
                    node.status = NodeStatus.DISCONNECTED
                    self.persistence.save_node(node)
                    logger.warning(f"Node {node.node_name} disconnected (heartbeat timeout)")

    def start_node_grace_period(self, node_name: str):
        """
        Start grace period for a node.

        Args:
            node_name: Node name

        Raises:
            NodeNotFoundException: If node not found
        """
        node = self.nodes.get(node_name)
        if not node:
            raise NodeNotFoundException(f"Node {node_name} not found")

        node.start_grace_period(self.config.worker.job_startup_grace)
        self.persistence.save_node(node)
        logger.debug(f"Grace period started for node {node_name}")

    def request_shutdown_all_workers(self):
        """
        Request shutdown for all worker nodes.
        Sets the shutdown_requested flag on all nodes so they will
        gracefully shutdown when they next poll/heartbeat.
        """
        for node in self.nodes.values():
            if node.status == NodeStatus.CONNECTED:
                node.shutdown_requested = True
                self.persistence.save_node(node)
                logger.info(f"Shutdown requested for node {node.node_name}")
        logger.info(f"Shutdown requested for {len(self.nodes)} worker nodes")
