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
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.head.scheduler import Scheduler
from scheduler.head.persistence import PersistenceManager
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
    return Config(
        address="localhost:8265",
        port=8265,
        temp_dir=temp_dir,
        log_dir=temp_dir,
        heartbeat_timeout=30,
        scheduling_interval=10,
        gpu_poll_interval=5,
        gpu_util_threshold=10.0,
        gpu_mem_threshold=10.0,
        gpu_stable_time=60,
        job_startup_grace=30
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
    gpus = [
        GPU(gpu_id=0, stats=sample_gpu_stats[0], stable_since=datetime.now()),
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
