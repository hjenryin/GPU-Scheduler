"""Unit tests for scheduler algorithm"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import (
    Job, Node, GPU, GPUStats, JobRequirement,
    JobStatus, NodeStatus
)
from scheduler.head.scheduler import Scheduler


class TestScheduler:
    """Tests for Scheduler class"""

    def test_schedule_cycle_no_pending_jobs(self, scheduler):
        """Test scheduling cycle with no pending jobs"""
        # Should not raise any exceptions
        scheduler.schedule_cycle()

    def test_schedule_simple_job(self, scheduler, job_manager, node_manager):
        """Test scheduling a simple job"""
        # Create a node with 2 free GPUs
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [
            GPU(0, stats, stable_since=stable_time),
            GPU(1, stats, stable_since=stable_time)
        ]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=2,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create a job requiring 2 GPUs
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling cycle
        scheduler.schedule_cycle()

        # Check job was scheduled
        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu1"
        assert len(updated_job.assigned_gpus) == 2

    def test_schedule_job_with_dependencies(self, scheduler, job_manager, node_manager):
        """Test job with dependencies is not scheduled until deps complete"""
        # Create node
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [GPU(0, stats, stable_since=stable_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job with dependency
        job = Job(
            job_id="job-002",
            name="dependent-job",
            script="/script.py",
            requirements=JobRequirement("1"),
            dependencies=["job-001"],
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling - should not schedule
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-002")
        assert updated_job.status == JobStatus.PENDING

        # Now mark dependency as completed
        dep_job = Job(
            job_id="job-001",
            name="dependency",
            script="/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.COMPLETED
        )
        job_manager.add_job(dep_job)

        # Run scheduling again - should schedule now
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-002")
        assert updated_job.status == JobStatus.RUNNING

    def test_schedule_node_in_grace_period(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled on node in grace period"""
        # Create node in grace period
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [GPU(0, stats, stable_since=stable_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node.start_grace_period(120)  # 2 minute grace period
        node_manager.register_node(node)

        # Create job
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling - should not schedule
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_insufficient_gpus(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled when insufficient GPUs available"""
        # Create node with only 1 GPU
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [GPU(0, stats, stable_since=stable_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job requiring 2 GPUs
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling - should not schedule
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_node_specific_requirement(self, scheduler, job_manager, node_manager):
        """Test scheduling with node-specific requirement"""
        # Create two nodes
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)

        for node_name in ["gpu1", "gpu2"]:
            gpus = [
                GPU(0, stats, stable_since=stable_time),
                GPU(1, stats, stable_since=stable_time)
            ]
            node = Node(
                node_name=node_name,
                address=f"192.168.1.{10 if node_name == 'gpu1' else 11}",
                num_gpus=2,
                gpus=gpus,
                status=NodeStatus.CONNECTED,
                last_heartbeat=datetime.now()
            )
            node_manager.register_node(node)

        # Create job requiring gpu2 specifically
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("gpu2:2"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu2"

    def test_schedule_alternative_requirements(self, scheduler, job_manager, node_manager):
        """Test scheduling with alternative requirements"""
        # Create only gpu2
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [
            GPU(0, stats, stable_since=stable_time),
            GPU(1, stats, stable_since=stable_time)
        ]

        node = Node(
            node_name="gpu2",
            address="192.168.1.11",
            num_gpus=2,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job with alternatives (gpu1:2 OR gpu2:2)
        # Since only gpu2 exists, should schedule on gpu2
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("gpu1:2,gpu2:2"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu2"

    def test_schedule_gpu_not_stable(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled on GPU that hasn't stabilized"""
        # Create node with GPU that just became free
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        recent_time = datetime.now() - timedelta(seconds=20)  # Only 20 seconds stable
        gpus = [GPU(0, stats, stable_since=recent_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        job_manager.add_job(job)

        # Run scheduling - should not schedule (needs 60s stability)
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job("job-001")
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_priority_order(self, scheduler, job_manager, node_manager):
        """Test jobs are scheduled in priority order"""
        # Create node with 1 GPU
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [GPU(0, stats, stable_since=stable_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create jobs with different priorities
        low_priority_job = Job(
            job_id="job-low",
            name="low-priority",
            script="/script.py",
            requirements=JobRequirement("1"),
            priority=1,
            status=JobStatus.PENDING
        )

        high_priority_job = Job(
            job_id="job-high",
            name="high-priority",
            script="/script.py",
            requirements=JobRequirement("1"),
            priority=10,
            status=JobStatus.PENDING
        )

        # Add low priority first
        job_manager.add_job(low_priority_job)
        job_manager.add_job(high_priority_job)

        # Run scheduling - high priority should be scheduled
        scheduler.schedule_cycle()

        low_job = job_manager.get_job("job-low")
        high_job = job_manager.get_job("job-high")

        assert high_job.status == JobStatus.RUNNING
        assert low_job.status == JobStatus.PENDING

    def test_find_suitable_node(self, scheduler, node_manager):
        """Test find_suitable_node method"""
        # Create node
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [
            GPU(0, stats, stable_since=stable_time),
            GPU(1, stats, stable_since=stable_time)
        ]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=2,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.PENDING
        )

        result = scheduler.find_suitable_node(job)

        assert result is not None
        node_name, gpu_ids = result
        assert node_name == "gpu1"
        assert len(gpu_ids) == 2

    def test_find_suitable_node_no_match(self, scheduler, node_manager):
        """Test find_suitable_node returns None when no match"""
        # Create node with only 1 GPU
        stats = GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        stable_time = datetime.now() - timedelta(seconds=70)
        gpus = [GPU(0, stats, stable_since=stable_time)]

        node = Node(
            node_name="gpu1",
            address="192.168.1.10",
            num_gpus=1,
            gpus=gpus,
            status=NodeStatus.CONNECTED,
            last_heartbeat=datetime.now()
        )
        node_manager.register_node(node)

        # Create job requiring 4 GPUs
        job = Job(
            job_id="job-001",
            name="test-job",
            script="/script.py",
            requirements=JobRequirement("4"),
            status=JobStatus.PENDING
        )

        result = scheduler.find_suitable_node(job)
        assert result is None
