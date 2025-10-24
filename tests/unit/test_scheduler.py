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
        # Register a node with 2 GPUs
        node_manager.register_node("gpu1", "192.168.1.10", 2)

        # Send heartbeat with stable GPUs
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        # Set GPUs as stable
        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit a job requiring 2 GPUs
        job = job_manager.submit_job(
            script="/script.py",
            requirements="2",
            name="test-job"
        )

        # Run scheduling cycle
        scheduler.schedule_cycle()

        # Check job was scheduled
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu1"
        assert len(updated_job.assigned_gpus) == 2

    def test_schedule_job_with_dependencies(self, scheduler, job_manager, node_manager):
        """Test job with dependencies is not scheduled until deps complete"""
        # Register node
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = stable_time

        # Submit dependency job first
        dep_job = job_manager.submit_job(
            script="/dep.py",
            requirements="1",
            name="dependency"
        )

        # Submit job with dependency
        job = job_manager.submit_job(
            script="/script.py",
            requirements="1",
            name="dependent-job",
            dependencies=[dep_job.job_id]
        )

        # Run scheduling - should not schedule dependent job
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

        # Complete dependency
        job_manager.complete_job(dep_job.job_id, exit_code=0)

        # Simulate GPU becoming free after job completes (detected by monitoring)
        # Reset GPU stability and clear grace period
        node = node_manager.get_node("gpu1")
        low_usage_stats = GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        node.gpus[0].update_stats(low_usage_stats, util_threshold=10.0, mem_threshold=10.0)
        node.gpus[0].stable_since = stable_time
        node.grace_period_until = None  # Clear grace period

        # Run scheduling again - should schedule now
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING

    def test_schedule_node_in_grace_period(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled on node in grace period"""
        # Register node and send heartbeat
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = stable_time

        # Start grace period
        node_manager.start_node_grace_period("gpu1")

        # Submit job
        job = job_manager.submit_job(
            script="/script.py",
            requirements="1",
            name="test-job"
        )

        # Run scheduling - should not schedule
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_insufficient_gpus(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled when insufficient GPUs available"""
        # Register node with only 1 GPU
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = stable_time

        # Submit job requiring 2 GPUs
        job = job_manager.submit_job(
            script="/script.py",
            requirements="2",
            name="test-job"
        )

        # Run scheduling - should not schedule
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_node_specific_requirement(self, scheduler, job_manager, node_manager):
        """Test scheduling with node-specific requirement"""
        # Register two nodes
        for node_name in ["gpu1", "gpu2"]:
            node_manager.register_node(node_name, f"192.168.1.{10 if node_name == 'gpu1' else 11}", 2)
            stats = [
                GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
                GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
            ]
            node_manager.update_heartbeat(node_name, stats)

            stable_time = datetime.now() - timedelta(seconds=70)
            node = node_manager.get_node(node_name)
            for gpu in node.gpus:
                gpu.stable_since = stable_time

        # Submit job requiring gpu2 specifically
        job = job_manager.submit_job(
            script="/script.py",
            requirements="gpu2:2",
            name="test-job"
        )

        # Run scheduling
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu2"

    def test_schedule_alternative_requirements(self, scheduler, job_manager, node_manager):
        """Test scheduling with alternative requirements"""
        # Register only gpu2
        node_manager.register_node("gpu2", "192.168.1.11", 2)
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu2", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu2")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit job with alternatives (gpu1:2 OR gpu2:2)
        # Since only gpu2 exists, should schedule on gpu2
        job = job_manager.submit_job(
            script="/script.py",
            requirements="gpu1:2,gpu2:2",
            name="test-job"
        )

        # Run scheduling
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu2"

    def test_schedule_gpu_not_stable(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled on GPU that hasn't stabilized"""
        # Register node with GPU that just became free
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        # Set recent stability time (only 20 seconds)
        recent_time = datetime.now() - timedelta(seconds=20)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = recent_time

        # Submit job
        job = job_manager.submit_job(
            script="/script.py",
            requirements="1",
            name="test-job"
        )

        # Run scheduling - should not schedule (needs 60s stability)
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_priority_order(self, scheduler, job_manager, node_manager):
        """Test jobs are scheduled in priority order"""
        # Register node with 1 GPU
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = stable_time

        # Submit jobs with different priorities (low priority first)
        low_priority_job = job_manager.submit_job(
            script="/low.py",
            requirements="1",
            name="low-priority",
            priority=1
        )

        high_priority_job = job_manager.submit_job(
            script="/high.py",
            requirements="1",
            name="high-priority",
            priority=10
        )

        # Run scheduling - high priority should be scheduled
        scheduler.schedule_cycle()

        low_job = job_manager.get_job(low_priority_job.job_id)
        high_job = job_manager.get_job(high_priority_job.job_id)

        assert high_job.status == JobStatus.RUNNING
        assert low_job.status == JobStatus.PENDING

    def test_find_suitable_node(self, scheduler, node_manager, job_manager):
        """Test find_suitable_node method"""
        # Register node
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit job
        job = job_manager.submit_job(
            script="/script.py",
            requirements="2",
            name="test-job"
        )

        result = scheduler.find_suitable_node(job)

        assert result is not None
        node_name, gpu_ids = result
        assert node_name == "gpu1"
        assert len(gpu_ids) == 2

    def test_find_suitable_node_no_match(self, scheduler, node_manager, job_manager):
        """Test find_suitable_node returns None when no match"""
        # Register node with only 1 GPU
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = stable_time

        # Submit job requiring 4 GPUs
        job = job_manager.submit_job(
            script="/script.py",
            requirements="4",
            name="test-job"
        )

        result = scheduler.find_suitable_node(job)
        assert result is None
