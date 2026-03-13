"""Unit tests for NodeManager"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import Node, GPU, GPUStats, NodeStatus, ShutdownState
from scheduler.core.exceptions import NodeNotFoundException
from scheduler.manager import NodeManager
from scheduler.manager import PersistenceManager


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
        """Test getting non-existent node returns None"""
        node = node_manager.get_node("nonexistent")
        assert node is None

    def test_list_all_nodes(self, node_manager):
        """Test listing all nodes"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        node_manager.register_node("gpu2", "192.168.1.11", 2)

        nodes = node_manager.list_nodes()

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
        """Test heartbeat for non-existent node is handled gracefully"""
        stats = [GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)]

        # Attempting to update heartbeat for non-existent node should not crash
        # The node manager should handle this gracefully
        try:
            node_manager.update_heartbeat("nonexistent", stats)
        except Exception as e:
            # If it raises an exception, it should be a specific one
            assert isinstance(e, (NodeNotFoundException, KeyError))

    def test_gpu_monitoring_based_availability(self, node_manager):
        """Test that GPU availability is based on actual monitoring, not assignments"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Initialize GPUs with low usage (free)
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        node = node_manager.get_node("gpu1")

        # Check that GPUs are considered free based on actual usage
        free_gpus = node.get_free_gpus(
            util_threshold=10.0,
            mem_threshold=10.0
        )
        assert len(free_gpus) == 4

        # Now simulate high usage on some GPUs
        high_usage_stats = [
            GPUStats(0, 85.0, 14*1024**3, 16*1024**3, 72, 280, 300),
            GPUStats(1, 90.0, 15*1024**3, 16*1024**3, 75, 290, 300),
            GPUStats(2, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(3, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
        ]
        node_manager.update_heartbeat("gpu1", high_usage_stats)

        # GPUs with high usage should not be considered free
        free_gpus = node.get_free_gpus(
            util_threshold=10.0,
            mem_threshold=10.0
        )
        assert 0 not in free_gpus
        assert 1 not in free_gpus

    def test_start_node_grace_period(self, node_manager, test_config):
        """Test starting grace period on a node"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        node_manager.start_node_grace_period("gpu1")

        node = node_manager.get_node("gpu1")
        assert node.is_in_grace_period() is True

    def test_check_timeouts(self, node_manager, test_config):
        """Test detecting disconnected nodes"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Send heartbeat
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Manually set last_heartbeat to old time
        node = node_manager.get_node("gpu1")
        node.last_heartbeat = datetime.now() - timedelta(seconds=100)

        # Check timeouts (should mark as disconnected)
        # check_timeouts() doesn't return anything, it modifies node status
        node_manager.check_timeouts()

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

    def test_multiple_heartbeats_update_gpu_stats(self, node_manager):
        """Test that multiple heartbeats properly update GPU statistics"""
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # First heartbeat with low usage
        stats1 = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats1)

        node = node_manager.get_node("gpu1")
        assert node.gpus[0].stats.utilization == 5.0

        # Second heartbeat with high usage
        stats2 = [GPUStats(i, 85.0, 14*1024**3, 16*1024**3, 72, 280, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats2)

        node = node_manager.get_node("gpu1")
        assert node.gpus[0].stats.utilization == 85.0
    def test_request_shutdown_all_workers(self, node_manager):
        """Test requesting shutdown for all worker nodes"""
        # Register some nodes
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        node_manager.register_node("gpu2", "192.168.1.20", 8)
        
        # Simulate heartbeat to mark nodes as connected
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)
        
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(8)]
        node_manager.update_heartbeat("gpu2", stats)
        
        # Verify nodes are connected and shutdown not requested
        node1 = node_manager.get_node("gpu1")
        node2 = node_manager.get_node("gpu2")
        assert node1.status == NodeStatus.CONNECTED
        assert node2.status == NodeStatus.CONNECTED
        assert node1.shutdown_state == ShutdownState.NONE
        assert node2.shutdown_state == ShutdownState.NONE
        
        # Request shutdown for all workers
        node_manager.request_shutdown_all_workers()
        
        # Verify shutdown was requested
        node1 = node_manager.get_node("gpu1")
        node2 = node_manager.get_node("gpu2")
        assert node1.shutdown_state != ShutdownState.NONE
        assert node2.shutdown_state != ShutdownState.NONE

    def test_reregister_clears_shutdown_flags(self, node_manager):
        """Test that re-registering a node clears shutdown flags"""
        # Register a node
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Simulate heartbeat to mark as connected
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Request shutdown
        node_manager.request_shutdown_all_workers()
        node1 = node_manager.get_node("gpu1")
        assert node1.shutdown_state != ShutdownState.NONE

        # Re-register the node (simulating worker restart)
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Verify shutdown flags are cleared
        node1 = node_manager.get_node("gpu1")
        assert node1.shutdown_state == ShutdownState.NONE
        assert node1.status == NodeStatus.CONNECTED
