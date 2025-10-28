"""Pytest fixtures for TUI testing."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from typing import List

from scheduler.core import Node, Job, GPU, GPUStats, JobStatus, NodeStatus, JobRequirement
from scheduler.api import SchedulerClient


@pytest.fixture
def mock_gpu_stats():
    """Create real GPU stats object."""
    stats = GPUStats(
        gpu_id=0,
        utilization=5.0,  # Low utilization, below 10% threshold
        memory_used=512 * 1024 ** 2,  # 512MB - low memory usage
        memory_total=8 * 1024 ** 3,  # 8GB
        temperature=65,
        power_draw=150,
        power_limit=300,
        running_job_id=None
    )
    return stats


@pytest.fixture
def mock_gpu(mock_gpu_stats):
    """Create real GPU object."""
    gpu = GPU(gpu_id=0, stats=mock_gpu_stats)
    # Set as stable (been free for 120 seconds to be sure)
    gpu.stable_since = datetime.now() - timedelta(seconds=120)
    return gpu


@pytest.fixture
def mock_gpu_occupied():
    """Create real occupied GPU object."""
    stats = GPUStats(
        gpu_id=1,
        utilization=85.0,
        memory_used=6 * 1024 ** 3,
        memory_total=8 * 1024 ** 3,
        temperature=75,
        power_draw=200,
        power_limit=300,
        running_job_id="job_123"
    )
    gpu = GPU(gpu_id=1, stats=stats)
    # Not stable (in use)
    gpu.stable_since = None
    return gpu


@pytest.fixture
def mock_gpus(mock_gpu, mock_gpu_occupied):
    """Create list of real GPU objects."""
    return [mock_gpu, mock_gpu_occupied]


@pytest.fixture
def mock_node(mock_gpus):
    """Create real node object with get_free_gpus method."""
    node = Node(
        node_name="gpu-server-01",
        address="192.168.1.100:8265",
        num_gpus=2,
        gpus=mock_gpus,
        status=NodeStatus.CONNECTED,
        last_heartbeat=datetime.now(),
        registered_at=datetime.now() - timedelta(hours=1)
    )
    return node


@pytest.fixture
def mock_node_disconnected(mock_gpus):
    """Create real disconnected node object."""
    # Create 4 GPUs for this node
    gpus = []
    for i in range(4):
        stats = GPUStats(i, 5.0, 500*1024**2, 16*1024**3, 60, 100, 300, None)  # 5% util, low mem
        gpu = GPU(i, stats)
        gpu.stable_since = datetime.now() - timedelta(seconds=120)  # Ensure stable
        gpus.append(gpu)
    
    node = Node(
        node_name="gpu-server-02",
        address="192.168.1.101:8265",
        num_gpus=4,
        gpus=gpus,
        status=NodeStatus.DISCONNECTED,
        last_heartbeat=datetime.now() - timedelta(minutes=10),
        registered_at=datetime.now() - timedelta(hours=2)
    )
    return node


@pytest.fixture
def mock_nodes(mock_node, mock_node_disconnected):
    """Create list of mock nodes."""
    return [mock_node, mock_node_disconnected]


@pytest.fixture
def mock_job_requirement():
    """Create mock job requirement."""
    req = Mock(spec=JobRequirement)
    req.num_gpus = 2
    req.alternatives = [{"node": "gpu-server-01", "num_gpus": 2}]
    return req


@pytest.fixture
def mock_job_pending(mock_job_requirement):
    """Create mock pending job."""
    job = Mock(spec=Job)
    job.job_id = "job_123"
    job.name = "test-training"
    job.status = JobStatus.PENDING
    job.assigned_node = None
    job.assigned_gpus = []
    job.requirements = mock_job_requirement
    job.submitted_at = datetime.now() - timedelta(minutes=5)
    job.runtime = None
    return job


@pytest.fixture
def mock_job_completed(mock_job_requirement):
    """Create mock completed job."""
    job = Mock(spec=Job)
    job.job_id = "job_789"
    job.name = "inference-job"
    job.status = JobStatus.COMPLETED
    job.assigned_node = "gpu-server-01"
    job.assigned_gpus = [0]
    job.requirements = mock_job_requirement
    job.submitted_at = datetime.now() - timedelta(hours=2)
    job.runtime = timedelta(minutes=30)
    return job


@pytest.fixture
def mock_job_failed(mock_job_requirement):
    """Create mock failed job."""
    job = Mock(spec=Job)
    job.job_id = "job_fail"
    job.name = "failed-experiment"
    job.status = JobStatus.FAILED
    job.assigned_node = "gpu-server-01"
    job.assigned_gpus = []
    job.requirements = mock_job_requirement
    job.submitted_at = datetime.now() - timedelta(hours=3)
    job.runtime = timedelta(minutes=5)
    return job


@pytest.fixture
def mock_job_running(mock_job_requirement):
    """Create mock running job."""
    job = Mock(spec=Job)
    job.job_id = "job_456"
    job.name = "bert-training"
    job.status = JobStatus.RUNNING
    job.assigned_node = "gpu-server-01"
    job.assigned_gpus = [0, 1]
    job.requirements = mock_job_requirement
    job.submitted_at = datetime.now() - timedelta(hours=1)
    job.runtime = timedelta(hours=1)
    return job


@pytest.fixture
def mock_jobs(mock_job_pending, mock_job_running, mock_job_completed, mock_job_failed):
    """Create list of mock jobs."""
    return [mock_job_pending, mock_job_running, mock_job_completed, mock_job_failed]


@pytest.fixture
def mock_scheduler_client(mock_nodes, mock_jobs):
    """Create mock SchedulerClient."""
    client = Mock(spec=SchedulerClient)
    client.list_nodes.return_value = mock_nodes
    client.list_jobs.return_value = mock_jobs
    client.get_job.return_value = mock_jobs[0]
    client.health_check.return_value = True
    return client


@pytest.fixture
def mock_scheduler_client_error():
    """Create mock SchedulerClient that raises errors."""
    client = Mock(spec=SchedulerClient)
    client.list_nodes.side_effect = Exception("Connection failed")
    client.list_jobs.side_effect = Exception("Connection failed")
    client.get_job.side_effect = Exception("Job not found")
    client.health_check.return_value = False
    return client


@pytest.fixture
def mock_textual_app():
    """Create mock Textual App for testing."""
    app = Mock()
    app.screen = Mock()
    app.screen.name = "cluster"
    app.switch_screen = Mock()
    app.push_screen = Mock()
    app.notify = Mock()
    app.exit = Mock()
    return app


@pytest.fixture
def mock_textual_screen():
    """Create mock Textual Screen for testing."""
    screen = Mock()
    screen.query_one = Mock()
    screen.update_data = Mock()
    screen.on_mount = Mock()
    return screen


@pytest.fixture
def mock_data_table():
    """Create mock DataTable widget."""
    table = Mock()
    table.add_columns = Mock()
    table.clear = Mock()
    table.add_row = Mock()
    table.cursor_type = "row"
    table.cursor_row = 0
    table.get_row = Mock(return_value=["job_123", "test-job", "running"])
    return table


@pytest.fixture
def mock_static_widget():
    """Create mock Static widget."""
    static = Mock()
    static.update = Mock()
    return static


@pytest.fixture
def mock_input_widget():
    """Create mock Input widget."""
    input_widget = Mock()
    input_widget.focus = Mock()
    input_widget.value = ""
    return input_widget


@pytest.fixture
def mock_container():
    """Create mock Container widget."""
    container = Mock()
    container.id = "test-container"
    return container


# Test data for specific scenarios
@pytest.fixture
def empty_cluster_data():
    """Create empty cluster data for testing."""
    return {
        "nodes": [],
        "jobs": []
    }


@pytest.fixture
def single_node_cluster_data(mock_node, mock_job_running):
    """Create single node cluster data."""
    return {
        "nodes": [mock_node],
        "jobs": [mock_job_running]
    }


@pytest.fixture
def multi_node_cluster_data(mock_nodes, mock_jobs):
    """Create multi-node cluster data."""
    return {
        "nodes": mock_nodes,
        "jobs": mock_jobs
    }


# Event fixtures for testing user interactions
@pytest.fixture
def mock_input_changed_event():
    """Create mock input changed event."""
    event = Mock()
    event.input = Mock()
    event.input.id = "search-input"
    event.value = "test search"
    return event


@pytest.fixture
def mock_row_selected_event():
    """Create mock row selected event."""
    event = Mock()
    event.data_table = Mock()
    event.data_table.id = "jobs-table"
    event.row_key = "job_123"
    event.row = 0
    return event


@pytest.fixture
def mock_key_event():
    """Create mock key event."""
    event = Mock()
    event.key = "j"
    return event
