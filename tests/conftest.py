"""Pytest configuration and shared fixtures"""
import pytest
import tempfile
import shutil
from datetime import datetime
from typing import List

from scheduler.core.models import (
    Job, Node, GPU, GPUStats, JobRequirement,
    JobStatus, NodeStatus
)
from scheduler.core.config import Config
from scheduler.manager import JobManager
from scheduler.manager import NodeManager
from scheduler.manager import Scheduler
from scheduler.manager import PersistenceManager
from scheduler.storage import FileBackend


@pytest.fixture
def temp_dir():
    """Temporary directory fixture"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def test_config(temp_dir):
    """Test configuration fixture"""
    from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig, ClientConfig
    from scheduler.core.utils import find_available_port

    # Find an available port for testing to avoid conflicts
    test_port = find_available_port(start_port=8000, max_attempts=100)
    
    return Config(
        address=f"localhost:{test_port}",
        head=HeadConfig(
            port=test_port,
            heartbeat_timeout=10,
            scheduling_interval=1,  # Faster for testing
            graceful_shutdown_timeout=10  # Faster for testing
        ),
        worker=WorkerConfig(
            temp_dir=temp_dir,
            log_dir=temp_dir,
            work_dir=temp_dir,
            heartbeat_interval=2,  # Must be <= gpu_stable_time
            gpu_poll_interval=2,
            gpu_util_threshold=10.0,
            gpu_mem_threshold=10.0,
            gpu_stable_time=2,  # Reduced from 60 for faster tests
            job_startup_grace=3  # Reduced from 30 for faster tests
        ),
        storage=StorageConfig(),
        client=ClientConfig()
    )


@pytest.fixture
def sample_gpu_stats() -> List[GPUStats]:
    """Sample GPU statistics"""
    return [
        GPUStats(
            gpu_id=0,
            utilization=5.0,
            memory_used=1024 * 1024 * 1024,  # 1 GB
            memory_total=16 * 1024 * 1024 * 1024,  # 16 GB
            temperature=45,
            power_draw=50,
            power_limit=300
        ),
        GPUStats(
            gpu_id=1,
            utilization=95.0,
            memory_used=15 * 1024 * 1024 * 1024,  # 15 GB
            memory_total=16 * 1024 * 1024 * 1024,  # 16 GB
            temperature=75,
            power_draw=280,
            power_limit=300
        )
    ]


@pytest.fixture
def sample_node(sample_gpu_stats) -> Node:
    """Sample node fixture"""
    # Create a GPU that's been stable for more than the stable time threshold (2 seconds for tests)
    from datetime import timedelta
    stable_time = datetime.now() - timedelta(seconds=3)
    
    gpus = [
        GPU(gpu_id=0, stats=sample_gpu_stats[0], stable_since=stable_time),
        GPU(gpu_id=1, stats=sample_gpu_stats[1])
    ]

    node = Node(
        node_name="gpu1",
        address="192.168.1.10",
        num_gpus=2,
        gpus=gpus,
        status=NodeStatus.CONNECTED,
        last_heartbeat=datetime.now()
    )
    return node


@pytest.fixture
def sample_job() -> Job:
    """Sample job fixture"""
    return Job(
        job_id="job-001",
        name="test-job",
        script="/path/to/script.py",
        requirements=JobRequirement("2"),
        script_args=["--epochs", "100"],
        working_dir="/home/user/project",
        env_vars={"PYTHONPATH": "/home/user/lib"},
        priority=1,
        status=JobStatus.PENDING
    )


@pytest.fixture
def persistence_manager(temp_dir, test_config):
    """PersistenceManager fixture"""
    backend = FileBackend(storage_dir=temp_dir)
    return PersistenceManager(backend=backend, config=test_config)


@pytest.fixture
def job_manager(persistence_manager, test_config):
    """JobManager fixture"""
    return JobManager(persistence=persistence_manager, config=test_config)


@pytest.fixture
def node_manager(persistence_manager, test_config):
    """NodeManager fixture"""
    return NodeManager(persistence=persistence_manager, config=test_config)


@pytest.fixture
def scheduler(job_manager, node_manager, test_config):
    """Scheduler fixture"""
    return Scheduler(job_manager, node_manager, test_config)
