"""Unit tests for NodeManager"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import Node, GPU, GPUStats, NodeStatus
from scheduler.core.exceptions import NodeNotFoundException
from scheduler.head.node_manager import NodeManager
from scheduler.head.persistence import PersistenceManager


@pytest.fixture
def persistence_manager(temp_dir, test_config):
    """Create persistence manager for testing"""
    from scheduler.storage import FileBackend
    backend = FileBackend(storage_dir=temp_dir)
    return PersistenceManager(backend=backend, config=test_config)


@pytest.fixture
def node_manager(persistence_manager, test_config):
    """Create node manager for testing"""
    return NodeManager(persistence=persistence_manager, config=test_config)


class TestNodeManager:
    """Tests for NodeManager class"""

    def test_register_new_node(self, node_manager):
        """Test registering a new node"""
        node = node_manager.register_node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=4
        )

        assert node.node_name == "gpu1"
        assert node.address == "192.168.1.10"
        assert node.num_gpus == 4
        assert node.status == NodeStatus.INITIALIZING
        assert node.registered_at is not None

    def test_register_existing_node(self, node_manager):
        """Test re-registering an existing node updates it"""
        # Register first time
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Re-register with different address
        node = node_manager.register_node("gpu1", "192.168.1.20", 4)

        assert node.address == "192.168.1.20"
        assert node.status == NodeStatus.CONNECTED

    def test_get_node(self, node_manager):
        """Test getting a node"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        node = node_manager.get_node("gpu1")

        assert node.node_name == "gpu1"

    def test_get_node_not_found(self, node_manager):
        """Test getting non-existent node raises exception"""
        with pytest.raises(NodeNotFoundException):
            node_manager.get_node("nonexistent")

    def test_get_all_nodes(self, node_manager):
        """Test getting all nodes"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        node_manager.register_node("gpu2", "192.168.1.11", 2)

        nodes = node_manager.get_all_nodes()

        assert len(nodes) == 2
        node_names = [n.node_name for n in nodes]
        assert "gpu1" in node_names
        assert "gpu2" in node_names

    def test_get_connected_nodes(self, node_manager):
        """Test getting only connected nodes"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        node_manager.register_node("gpu2", "192.168.1.11", 2)

        # Update heartbeat for gpu1 (makes it connected)
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        connected = node_manager.get_connected_nodes()

        # Only gpu1 should be connected (received heartbeat)
        # gpu2 is still initializing
        assert len(connected) == 1
        assert connected[0].node_name == "gpu1"

    def test_update_heartbeat(self, node_manager):
        """Test updating node heartbeat"""
        node_manager.register_node("gpu1", "192.168.1.10", 2)

        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 10.0, 2*1024**3, 16*1024**3, 50, 60, 300)
        ]

        node_manager.update_heartbeat("gpu1", stats)

        node = node_manager.get_node("gpu1")
        assert node.status == NodeStatus.CONNECTED
        assert node.last_heartbeat is not None
        assert len(node.gpus) == 2
        assert node.gpus[0].stats.utilization == 5.0
        assert node.gpus[1].stats.utilization == 10.0

    def test_update_heartbeat_initializes_gpus(self, node_manager):
        """Test first heartbeat initializes GPU objects"""
        node_manager.register_node("gpu1", "192.168.1.10", 2)

        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]

        node_manager.update_heartbeat("gpu1", stats)

        node = node_manager.get_node("gpu1")
        assert len(node.gpus) == 2
        assert isinstance(node.gpus[0], GPU)
        assert isinstance(node.gpus[1], GPU)

    def test_update_heartbeat_not_found(self, node_manager):
        """Test heartbeat for non-existent node raises exception"""
        stats = [GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)]

        with pytest.raises(NodeNotFoundException):
            node_manager.update_heartbeat("nonexistent", stats)

    def test_assign_gpus_to_job(self, node_manager):
        """Test assigning GPUs to a job"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Initialize GPUs with heartbeat
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Assign GPUs
        node_manager.assign_gpus_to_job("gpu1", [0, 1], "job-001")

        node = node_manager.get_node("gpu1")
        assert node.gpus[0].assigned_job_id == "job-001"
        assert node.gpus[1].assigned_job_id == "job-001"
        assert node.gpus[2].assigned_job_id is None

    def test_release_gpus_from_job(self, node_manager):
        """Test releasing GPUs from a job"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Assign and then release
        node_manager.assign_gpus_to_job("gpu1", [0, 1], "job-001")
        node_manager.release_gpus_from_job("gpu1", [0, 1])

        node = node_manager.get_node("gpu1")
        assert node.gpus[0].assigned_job_id is None
        assert node.gpus[1].assigned_job_id is None

    def test_start_node_grace_period(self, node_manager, test_config):
        """Test starting grace period on a node"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        node_manager.start_node_grace_period("gpu1")

        node = node_manager.get_node("gpu1")
        assert node.is_in_grace_period() is True

    def test_check_node_timeouts(self, node_manager, test_config):
        """Test detecting disconnected nodes"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Send heartbeat
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Manually set last_heartbeat to old time
        node = node_manager.get_node("gpu1")
        node.last_heartbeat = datetime.now() - timedelta(seconds=100)

        # Check timeouts (should mark as disconnected)
        disconnected = node_manager.check_node_timeouts()

        assert len(disconnected) == 1
        assert disconnected[0] == "gpu1"

        updated_node = node_manager.get_node("gpu1")
        assert updated_node.status == NodeStatus.DISCONNECTED

    def test_get_node_by_name(self, node_manager):
        """Test getting specific node by name"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        node_manager.register_node("gpu2", "192.168.1.11", 2)

        node = node_manager.get_node("gpu2")

        assert node.node_name == "gpu2"
        assert node.num_gpus == 2

    def test_persistence_integration(self, persistence_manager, test_config):
        """Test nodes are persisted and loaded"""
        # Create first manager and add node
        manager1 = NodeManager(persistence=persistence_manager, config=test_config)
        manager1.register_node("gpu1", "192.168.1.10", 4)

        # Create second manager (simulates restart)
        manager2 = NodeManager(persistence=persistence_manager, config=test_config)

        # Node should be loaded
        node = manager2.get_node("gpu1")
        assert node.node_name == "gpu1"
        assert node.address == "192.168.1.10"

    def test_get_jobs_on_node(self, node_manager):
        """Test getting jobs assigned to a node"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Assign different jobs to different GPUs
        node_manager.assign_gpus_to_job("gpu1", [0, 1], "job-001")
        node_manager.assign_gpus_to_job("gpu1", [2], "job-002")

        jobs = node_manager.get_jobs_on_node("gpu1")

        assert len(jobs) == 2
        assert "job-001" in jobs
        assert "job-002" in jobs

    def test_gpu_stability_tracking(self, node_manager):
        """Test GPU stability is tracked through heartbeats"""
        node_manager.register_node("gpu1", "192.168.1.10", 2)

        # First heartbeat - GPUs become stable
        stats1 = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 95.0, 15*1024**3, 16*1024**3, 75, 280, 300)  # Busy
        ]
        node_manager.update_heartbeat("gpu1", stats1)

        node = node_manager.get_node("gpu1")
        # GPU 0 should start tracking stability
        assert node.gpus[0].stable_since is not None
        # GPU 1 is busy, should not be stable
        assert node.gpus[1].stable_since is None

        # Second heartbeat - GPU 1 becomes free
        stats2 = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 3.0, 0.5*1024**3, 16*1024**3, 40, 30, 300)  # Now free
        ]
        node_manager.update_heartbeat("gpu1", stats2)

        node = node_manager.get_node("gpu1")
        # GPU 1 should now start tracking stability
        assert node.gpus[1].stable_since is not None
