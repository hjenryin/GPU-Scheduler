"""Simple unit tests for TUI widgets"""
import pytest
from unittest.mock import Mock, patch

from scheduler.tui.widgets.job_table import JobTable
from scheduler.tui.widgets.node_table import NodeTable
from scheduler.tui.widgets.gpu_bar import GPUBar
from scheduler.core.models import Job, JobStatus, Node, NodeStatus, GPU, GPUStats


class TestJobTableSimple:
    """Simple tests for JobTable widget"""

    @pytest.fixture
    def job_table(self):
        """Create a JobTable instance"""
        return JobTable()

    def test_init(self, job_table):
        """Test JobTable initialization"""
        assert job_table._columns_setup is False

    def test_setup_columns(self, job_table):
        """Test column setup"""
        with patch.object(job_table, 'add_columns') as mock_add_columns:
            job_table._setup_columns()
            
            mock_add_columns.assert_called_once_with("Job ID", "Name", "Status", "Node", "GPUs", "Runtime")
            assert job_table.cursor_type == "row"
            assert job_table._columns_setup is True

    def test_setup_columns_already_setup(self, job_table):
        """Test column setup when already setup"""
        job_table._columns_setup = True
        
        with patch.object(job_table, 'add_columns') as mock_add_columns:
            job_table._setup_columns()
            
            mock_add_columns.assert_not_called()

    def test_update_jobs(self, job_table):
        """Test update_jobs method"""
        # Create mock jobs with required attributes
        mock_jobs = []
        for i in range(3):
            job = Mock(spec=Job)
            job.job_id = f"job-{i:03d}"
            job.name = f"Test Job {i}"
            job.status = JobStatus.PENDING
            job.assigned_node = None
            job.num_gpus = 1
            job.runtime = None
            job.requirements = Mock()
            job.requirements.num_gpus = 1
            mock_jobs.append(job)
        
        with patch.object(job_table, '_setup_columns') as mock_setup, \
             patch.object(job_table, 'clear') as mock_clear, \
             patch.object(job_table, 'add_row') as mock_add_row:
            
            job_table.update_jobs(mock_jobs)
            
            mock_setup.assert_called_once()
            mock_clear.assert_called_once()
            assert mock_add_row.call_count == 3


class TestNodeTableSimple:
    """Simple tests for NodeTable widget"""

    @pytest.fixture
    def node_table(self):
        """Create a NodeTable instance"""
        return NodeTable()

    def test_init(self, node_table):
        """Test NodeTable initialization"""
        assert node_table._columns_setup is False

    def test_setup_columns(self, node_table):
        """Test column setup"""
        with patch.object(node_table, 'add_columns') as mock_add_columns:
            node_table._setup_columns()
            
            mock_add_columns.assert_called_once_with("Node", "Status", "GPUs", "Free", "Running", "Last Heartbeat")
            assert node_table.cursor_type == "row"
            assert node_table._columns_setup is True

    def test_update_nodes(self, node_table):
        """Test update_nodes method"""
        # Create mock nodes with required attributes
        mock_nodes = []
        for i in range(2):
            node = Mock(spec=Node)
            node.node_name = f"worker-{i}"
            node.status = NodeStatus.CONNECTED
            node.num_gpus = 2
            node.last_heartbeat = "2024-01-01T10:00:00Z"
            node.gpus = []
            node.get_free_gpus.return_value = [0]
            mock_nodes.append(node)
        
        with patch.object(node_table, '_setup_columns') as mock_setup, \
             patch.object(node_table, 'clear') as mock_clear, \
             patch.object(node_table, 'add_row') as mock_add_row:
            
            node_table.update_nodes(mock_nodes)
            
            mock_setup.assert_called_once()
            mock_clear.assert_called_once()
            assert mock_add_row.call_count == 2


class TestGPUBarSimple:
    """Simple tests for GPUBar widget"""

    @pytest.fixture
    def gpu_bar(self):
        """Create a GPUBar instance"""
        return GPUBar(gpu_id=0, utilization=50.0, memory_used=8192, memory_total=16384)

    def test_init(self, gpu_bar):
        """Test GPUBar initialization"""
        assert gpu_bar.gpu_id == 0
        assert gpu_bar.utilization == 50.0
        assert gpu_bar.memory_used == 8192
        assert gpu_bar.memory_total == 16384

    def test_init_with_custom_values(self):
        """Test GPUBar initialization with custom values"""
        gpu_bar = GPUBar(gpu_id=1, utilization=75.5, memory_used=12288, memory_total=16384)
        assert gpu_bar.gpu_id == 1
        assert gpu_bar.utilization == 75.5
        assert gpu_bar.memory_used == 12288
        assert gpu_bar.memory_total == 16384
