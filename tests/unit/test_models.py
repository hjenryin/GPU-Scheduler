"""Unit tests for core models"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import (
    GPUStats, GPU, JobRequirement, Job, Node,
    JobStatus, NodeStatus
)
from scheduler.core.exceptions import InvalidRequirementException


class TestGPUStats:
    """Tests for GPUStats class"""

    def test_gpu_stats_creation(self):
        """Test GPU stats creation"""
        stats = GPUStats(
            gpu_id=0,
            utilization=50.0,
            memory_used=8 * 1024**3,  # 8 GB
            memory_total=16 * 1024**3,  # 16 GB
            temperature=65,
            power_draw=150,
            power_limit=300
        )

        assert stats.gpu_id == 0
        assert stats.utilization == 50.0
        assert stats.memory_used == 8 * 1024**3
        assert stats.memory_total == 16 * 1024**3
        assert stats.temperature == 65
        assert stats.power_draw == 150
        assert stats.power_limit == 300

    def test_gpu_stats_to_dict(self):
        """Test GPU stats serialization"""
        stats = GPUStats(0, 50.0, 8 * 1024**3, 16 * 1024**3, 65, 150, 300)
        data = stats.to_dict()

        assert data['gpu_id'] == 0
        assert data['utilization'] == 50.0
        assert data['memory_used'] == 8 * 1024**3
        assert data['temperature'] == 65

    def test_gpu_stats_from_dict(self):
        """Test GPU stats deserialization"""
        data = {
            'gpu_id': 1,
            'utilization': 75.0,
            'memory_used': 12 * 1024**3,
            'memory_total': 16 * 1024**3,
            'temperature': 70,
            'power_draw': 200,
            'power_limit': 300
        }

        stats = GPUStats.from_dict(data)
        assert stats.gpu_id == 1
        assert stats.utilization == 75.0
        assert stats.memory_used == 12 * 1024**3

    def test_is_free_below_thresholds(self):
        """Test GPU is considered free when below thresholds"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        assert stats.is_free(util_threshold=10.0, mem_threshold=10.0) is True

    def test_is_free_above_util_threshold(self):
        """Test GPU is not free when utilization above threshold"""
        stats = GPUStats(0, 50.0, 1 * 1024**3, 16 * 1024**3, 65, 150, 300)
        assert stats.is_free(util_threshold=10.0, mem_threshold=10.0) is False

    def test_is_free_above_mem_threshold(self):
        """Test GPU is not free when memory above threshold"""
        stats = GPUStats(0, 5.0, 8 * 1024**3, 16 * 1024**3, 45, 50, 300)
        # 8/16 = 50% memory usage, threshold is 10%
        assert stats.is_free(util_threshold=10.0, mem_threshold=10.0) is False


class TestGPU:
    """Tests for GPU class"""

    def test_gpu_creation(self):
        """Test GPU creation"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpu = GPU(gpu_id=0, stats=stats)

        assert gpu.gpu_id == 0
        assert gpu.stats == stats
        assert gpu.assigned_job_id is None
        assert gpu.stable_since is None

    def test_update_stats_becomes_stable(self):
        """Test GPU becomes stable when below threshold"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpu = GPU(gpu_id=0, stats=stats)

        # Update with low utilization
        new_stats = GPUStats(0, 3.0, 0.5 * 1024**3, 16 * 1024**3, 40, 30, 300)
        gpu.update_stats(new_stats, util_threshold=10.0, mem_threshold=10.0)

        assert gpu.stable_since is not None

    def test_update_stats_loses_stability(self):
        """Test GPU loses stability when above threshold"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpu = GPU(gpu_id=0, stats=stats, stable_since=datetime.now())

        # Update with high utilization
        new_stats = GPUStats(0, 90.0, 12 * 1024**3, 16 * 1024**3, 75, 250, 300)
        gpu.update_stats(new_stats, util_threshold=10.0, mem_threshold=10.0)

        assert gpu.stable_since is None

    def test_is_stable_after_duration(self):
        """Test GPU stability after required duration"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=65)
        gpu = GPU(gpu_id=0, stats=stats, stable_since=stable_time)

        assert gpu.is_stable(stable_time=60) is True

    def test_is_not_stable_before_duration(self):
        """Test GPU not stable before required duration"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=30)
        gpu = GPU(gpu_id=0, stats=stats, stable_since=stable_time)

        assert gpu.is_stable(stable_time=60) is False

    def test_gpu_serialization(self):
        """Test GPU to_dict and from_dict"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpu = GPU(gpu_id=0, stats=stats, assigned_job_id="job-001")

        data = gpu.to_dict()
        gpu_restored = GPU.from_dict(data)

        assert gpu_restored.gpu_id == 0
        assert gpu_restored.assigned_job_id == "job-001"
        assert gpu_restored.stats.utilization == 5.0


class TestJobRequirement:
    """Tests for JobRequirement class"""

    def test_simple_requirement(self):
        """Test simple GPU count requirement"""
        req = JobRequirement("2")
        assert len(req.alternatives) == 1
        assert req.alternatives[0] == (None, 2)

    def test_node_specific_requirement(self):
        """Test node-specific requirement"""
        req = JobRequirement("gpu1:4")
        assert len(req.alternatives) == 1
        assert req.alternatives[0] == ("gpu1", 4)

    def test_multiple_alternatives(self):
        """Test multiple alternative requirements"""
        req = JobRequirement("gpu1:2,gpu2:4")
        assert len(req.alternatives) == 2
        assert req.alternatives[0] == ("gpu1", 2)
        assert req.alternatives[1] == ("gpu2", 4)

    def test_mixed_alternatives(self):
        """Test mixed alternatives (any node and specific node)"""
        req = JobRequirement("2,gpu1:4")
        assert len(req.alternatives) == 2
        assert req.alternatives[0] == (None, 2)
        assert req.alternatives[1] == ("gpu1", 4)

    def test_invalid_empty_requirement(self):
        """Test invalid empty requirement"""
        with pytest.raises(InvalidRequirementException):
            JobRequirement("")

    def test_invalid_negative_count(self):
        """Test invalid negative GPU count"""
        with pytest.raises(InvalidRequirementException):
            JobRequirement("-2")

    def test_invalid_zero_count(self):
        """Test invalid zero GPU count"""
        with pytest.raises(InvalidRequirementException):
            JobRequirement("0")

    def test_invalid_non_numeric(self):
        """Test invalid non-numeric requirement"""
        with pytest.raises(InvalidRequirementException):
            JobRequirement("abc")

    def test_matches_node_any_node(self):
        """Test requirement matches any node"""
        req = JobRequirement("2")
        assert req.matches_node("gpu1", available_gpus=2) is True
        assert req.matches_node("gpu2", available_gpus=3) is True
        assert req.matches_node("gpu1", available_gpus=1) is False

    def test_matches_node_specific(self):
        """Test requirement matches specific node"""
        req = JobRequirement("gpu1:4")
        assert req.matches_node("gpu1", available_gpus=4) is True
        assert req.matches_node("gpu1", available_gpus=5) is True
        assert req.matches_node("gpu2", available_gpus=4) is False
        assert req.matches_node("gpu1", available_gpus=3) is False

    def test_matches_node_alternatives(self):
        """Test requirement with alternatives"""
        req = JobRequirement("gpu1:2,gpu2:4")
        assert req.matches_node("gpu1", available_gpus=2) is True
        assert req.matches_node("gpu2", available_gpus=4) is True
        assert req.matches_node("gpu3", available_gpus=4) is False


class TestJob:
    """Tests for Job class"""

    def test_job_creation(self):
        """Test job creation with minimal parameters"""
        req = JobRequirement("2")
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=req
        )

        assert job.job_id == "job-001"
        assert job.name == "test-job"
        assert job.script == "/path/to/script.py"
        assert job.status == JobStatus.PENDING
        assert job.script_args == []
        assert job.env_vars == {}
        assert job.dependencies == []

    def test_job_runtime_not_started(self):
        """Test runtime when job hasn't started"""
        req = JobRequirement("2")
        job = Job("job-001", "test", "/script.py", req)

        assert job.get_runtime() is None

    def test_job_runtime_running(self):
        """Test runtime for running job"""
        req = JobRequirement("2")
        started = datetime.now() - timedelta(seconds=100)
        job = Job(
            "job-001", "test", "/script.py", req,
            started_at=started,
            status=JobStatus.RUNNING
        )

        runtime = job.get_runtime()
        assert runtime is not None
        assert runtime.total_seconds() >= 100

    def test_job_runtime_completed(self):
        """Test runtime for completed job"""
        req = JobRequirement("2")
        started = datetime.now() - timedelta(seconds=200)
        completed = datetime.now() - timedelta(seconds=50)
        job = Job(
            "job-001", "test", "/script.py", req,
            started_at=started,
            completed_at=completed,
            status=JobStatus.COMPLETED
        )

        runtime = job.get_runtime()
        assert runtime is not None
        # Runtime should be ~150 seconds (200 - 50)
        assert 140 <= runtime.total_seconds() <= 160

    def test_can_start_no_dependencies(self):
        """Test job can start with no dependencies"""
        req = JobRequirement("2")
        job = Job("job-001", "test", "/script.py", req)

        assert job.can_start(set()) is True

    def test_can_start_dependencies_satisfied(self):
        """Test job can start when dependencies satisfied"""
        req = JobRequirement("2")
        job = Job(
            "job-001", "test", "/script.py", req,
            dependencies=["job-000"]
        )

        assert job.can_start({"job-000"}) is True

    def test_can_start_dependencies_not_satisfied(self):
        """Test job cannot start when dependencies not satisfied"""
        req = JobRequirement("2")
        job = Job(
            "job-001", "test", "/script.py", req,
            dependencies=["job-000"]
        )

        assert job.can_start(set()) is False
        assert job.can_start({"job-999"}) is False

    def test_job_serialization(self):
        """Test job to_dict and from_dict"""
        req = JobRequirement("gpu1:2")
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=req,
            script_args=["--epochs", "100"],
            env_vars={"KEY": "value"},
            priority=5
        )

        data = job.to_dict()
        job_restored = Job.from_dict(data)

        assert job_restored.job_id == "job-001"
        assert job_restored.name == "test-job"
        assert job_restored.script_args == ["--epochs", "100"]
        assert job_restored.env_vars == {"KEY": "value"}
        assert job_restored.priority == 5


class TestNode:
    """Tests for Node class"""

    def test_node_creation(self):
        """Test node creation"""
        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=4
        )

        assert node.node_name == "gpu1"
        assert node.address == "192.168.1.10"
        assert node.num_gpus == 4
        assert node.status == NodeStatus.INITIALIZING
        assert len(node.gpus) == 0

    def test_update_heartbeat(self):
        """Test heartbeat update"""
        stats_list = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 10.0, 2 * 1024**3, 16 * 1024**3, 50, 60, 300)
        ]

        gpus = [GPU(0, stats_list[0]), GPU(1, stats_list[1])]
        node = Node("gpu1", "192.168.1.10", 2, gpus=gpus)

        new_stats = [
            GPUStats(0, 3.0, 0.5 * 1024**3, 16 * 1024**3, 40, 30, 300),
            GPUStats(1, 8.0, 1.5 * 1024**3, 16 * 1024**3, 48, 55, 300)
        ]

        node.update_heartbeat(new_stats)

        assert node.status == NodeStatus.CONNECTED
        assert node.last_heartbeat is not None
        assert node.gpus[0].stats.utilization == 3.0
        assert node.gpus[1].stats.utilization == 8.0

    def test_get_free_gpus(self):
        """Test getting free GPUs"""
        # Create GPUs with different states
        stats_free = GPUStats(0, 3.0, 0.5 * 1024**3, 16 * 1024**3, 40, 30, 300)
        stats_busy = GPUStats(1, 90.0, 14 * 1024**3, 16 * 1024**3, 75, 250, 300)

        stable_time = datetime.now() - timedelta(seconds=70)
        gpu_free = GPU(0, stats_free, stable_since=stable_time)
        gpu_busy = GPU(1, stats_busy)

        node = Node("gpu1", "192.168.1.10", 2, gpus=[gpu_free, gpu_busy])

        free_gpus = node.get_free_gpus(
            util_threshold=10.0,
            mem_threshold=10.0,
            stable_time=60
        )

        assert free_gpus == [0]

    def test_grace_period(self):
        """Test grace period functionality"""
        node = Node("gpu1", "192.168.1.10", 4)

        assert node.is_in_grace_period() is False

        node.start_grace_period(duration=120)
        assert node.is_in_grace_period() is True

        # Set grace period to expired
        node.grace_period_until = datetime.now() - timedelta(seconds=10)
        assert node.is_in_grace_period() is False

    def test_assign_and_release_gpus(self):
        """Test GPU assignment and release"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpus = [GPU(i, stats) for i in range(4)]
        node = Node("gpu1", "192.168.1.10", 4, gpus=gpus)

        # Assign GPUs to job
        node.assign_gpus([0, 1], "job-001")

        assert node.gpus[0].assigned_job_id == "job-001"
        assert node.gpus[1].assigned_job_id == "job-001"
        assert node.gpus[2].assigned_job_id is None
        assert node.gpus[0].stable_since is None  # Reset on assignment

        # Release GPUs
        node.release_gpus([0, 1])

        assert node.gpus[0].assigned_job_id is None
        assert node.gpus[1].assigned_job_id is None

    def test_node_serialization(self):
        """Test node to_dict and from_dict"""
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        gpus = [GPU(i, stats) for i in range(2)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=2,
            gpus=gpus,
            status=NodeStatus.CONNECTED
        )

        data = node.to_dict()
        node_restored = Node.from_dict(data)

        assert node_restored.node_name == "gpu1"
        assert node_restored.address == "192.168.1.10"
        assert node_restored.num_gpus == 2
        assert len(node_restored.gpus) == 2
        assert node_restored.status == NodeStatus.CONNECTED
