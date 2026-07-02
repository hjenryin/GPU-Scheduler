"""Unit tests for scheduler algorithm"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import (
    Job, Node, GPU, GPUStats, JobRequirement,
    JobStatus, NodeStatus
)
from scheduler.manager import Scheduler


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

        # Send heartbeat with idle GPUs
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)



        # Submit a job requiring 2 GPUs
        job = job_manager.submit_job(
            command=["/script.py"],
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

        node = node_manager.get_node("gpu1")

        # Submit dependency job first
        dep_job = job_manager.submit_job(
            command=["/dep.py"],
            requirements="1",
            name="dependency"
        )

        # Submit job with dependency
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="1",
            name="dependent-job",
            dependencies=[dep_job.job_id]
        )

        # Run scheduling - should not schedule dependent job
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

        # Register terminal callback to simulate Orchestrator behavior
        def _on_job_terminal(j):
            if j.assigned_node and j.assigned_gpus:
                n = node_manager.get_node(j.assigned_node)
                if n:
                    for gpu_id in j.assigned_gpus:
                        if gpu_id < len(n.gpus) and n.gpus[gpu_id].assigned_job_id == j.job_id:
                            n.gpus[gpu_id].unassign()
                    node_manager.save_node(n)
        job_manager.on_job_terminal_callback = _on_job_terminal

        # Complete dependency
        job_manager.complete_job(dep_job.job_id, exit_code=0)

        # Simulate GPU becoming free after job completes (detected by monitoring)
        # Reset GPU stability and clear grace period
        node = node_manager.get_node("gpu1")
        low_usage_stats = GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        node.gpus[0].update_stats(low_usage_stats)
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

        node = node_manager.get_node("gpu1")

        # Start grace period
        node_manager.start_node_grace_period("gpu1")

        # Submit job
        job = job_manager.submit_job(
            command=["/script.py"],
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

        node = node_manager.get_node("gpu1")

        # Submit job requiring 2 GPUs
        job = job_manager.submit_job(
            command=["/script.py"],
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

            node = node_manager.get_node(node_name)

        # Submit job requiring gpu2 specifically
        job = job_manager.submit_job(
            command=["/script.py"],
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

        node = node_manager.get_node("gpu2")

        # Submit job with alternatives (gpu1:2 OR gpu2:2)
        # Since only gpu2 exists, should schedule on gpu2
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="gpu1:2,gpu2:2",
            name="test-job"
        )

        # Run scheduling
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu2"

    def test_schedule_priority_order(self, scheduler, job_manager, node_manager):
        """Test jobs are scheduled in priority order"""
        # Register node with 1 GPU
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        node = node_manager.get_node("gpu1")

        # Submit jobs with different priorities (low priority first)
        low_priority_job = job_manager.submit_job(
            command=["/low.py"],
            requirements="1",
            name="low-priority",
            priority=1
        )

        high_priority_job = job_manager.submit_job(
            command=["/high.py"],
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

        node = node_manager.get_node("gpu1")

        # Submit job
        job = job_manager.submit_job(
            command=["/script.py"],
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

        node = node_manager.get_node("gpu1")

        # Submit job requiring 4 GPUs
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="4",
            name="test-job"
        )

        result = scheduler.find_suitable_node(job)
        assert result is None

    def test_schedule_gpu_not_stable(self, scheduler, job_manager, node_manager):
        """Test job is not scheduled on GPU that hasn't stabilized"""
        from datetime import timedelta
        from dataclasses import asdict
        # Set stable time to 2 seconds
        scheduler.config = scheduler.config.from_dict({
            **scheduler.config.to_dict(),
            'worker': {
                **asdict(scheduler.config.worker),
                'gpu_stable_time': 2
            }
        })
        
        # Register node with GPU
        node_manager.register_node("gpu1", "192.168.1.10", 1)
        stats = [GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)]
        node_manager.update_heartbeat("gpu1", stats)

        # Set recent stability time (only 1 second, less than stable_time=2)
        recent_time = datetime.now() - timedelta(seconds=1)
        node = node_manager.get_node("gpu1")
        node.gpus[0].stable_since = recent_time
        node_manager.save_node(node)

        # Submit job
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="1",
            name="test-job"
        )

        # Run scheduling - should not schedule (needs 2s stability)
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

        # Set older stability time (3 seconds, greater than stable_time=2)
        stable_time = datetime.now() - timedelta(seconds=3)
        node.gpus[0].stable_since = stable_time
        node_manager.save_node(node)

        # Run scheduling - should schedule now
        scheduler.schedule_cycle()

        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING

    def test_schedule_stabilizing_gpus_defer(self, scheduler, job_manager, node_manager):
        """Test job scheduling is deferred when waiting for stabilizing GPUs would yield a larger configuration"""
        from dataclasses import asdict
        
        # Set stable time to 10 seconds
        scheduler.config = scheduler.config.from_dict({
            **scheduler.config.to_dict(),
            'worker': {
                **asdict(scheduler.config.worker),
                'gpu_stable_time': 10
            }
        })
        
        # Register node with 4 GPUs
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        
        # 3 GPUs are free and stable, 1 is free but stabilizing (waiting)
        # Note: GPU index 3 is recent (not stable), GPU index 0,1,2 are stable
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(2, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(3, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)
        
        node = node_manager.get_node("gpu1")
        # Stable for 20 seconds (greater than 10)
        node.gpus[0].stable_since = datetime.now() - timedelta(seconds=20)
        node.gpus[1].stable_since = datetime.now() - timedelta(seconds=20)
        node.gpus[2].stable_since = datetime.now() - timedelta(seconds=20)
        # Stabilizing (only stable for 2 seconds, less than 10)
        node.gpus[3].stable_since = datetime.now() - timedelta(seconds=2)
        node_manager.save_node(node)
        
        # Submit job with requirement alternatives "2,4"
        # Node has z=3 free stable, k=1 waiting
        # max{x_i <= z} = max{x_i <= 3} = 2
        # max{x_i <= z+k} = max{x_i <= 4} = 4
        # 2 != 4, so scheduling should be deferred (PENDING status)
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="2,4",
            name="test-job"
        )
        
        scheduler.schedule_cycle()
        
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

    def test_schedule_stabilizing_gpus_no_defer(self, scheduler, job_manager, node_manager):
        """Test job scheduling is NOT deferred when waiting for stabilizing GPUs would not yield a larger configuration"""
        from dataclasses import asdict
        
        # Set stable time to 10 seconds
        scheduler.config = scheduler.config.from_dict({
            **scheduler.config.to_dict(),
            'worker': {
                **asdict(scheduler.config.worker),
                'gpu_stable_time': 10
            }
        })
        
        # Register node with 4 GPUs
        node_manager.register_node("gpu1", "192.168.1.10", 4)
        
        # 2 GPUs are free and stable, 1 is free but stabilizing (waiting), 1 is busy
        # Note: GPU index 2 is recent (not stable), GPU index 0,1 are stable
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(2, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(3, 95.0, 15 * 1024**3, 16 * 1024**3, 75, 250, 300) # Busy
        ]
        node_manager.update_heartbeat("gpu1", stats)
        
        node = node_manager.get_node("gpu1")
        # Stable
        node.gpus[0].stable_since = datetime.now() - timedelta(seconds=20)
        node.gpus[1].stable_since = datetime.now() - timedelta(seconds=20)
        # Stabilizing
        node.gpus[2].stable_since = datetime.now() - timedelta(seconds=2)
        # Busy (no stable_since)
        node.gpus[3].stable_since = None
        node_manager.save_node(node)
        
        # Submit job with requirement alternatives "2,4"
        # Node has z=2 free stable, k=1 waiting
        # max{x_i <= z} = max{x_i <= 2} = 2
        # max{x_i <= z+k} = max{x_i <= 3} = 2
        # 2 == 2, so scheduling should NOT be deferred (RUNNING status)
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="2,4",
            name="test-job"
        )
        
        scheduler.schedule_cycle()
        
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert len(updated_job.assigned_gpus) == 2

    def test_schedule_stabilizing_gpus_flexible_defer(self, scheduler, job_manager, node_manager):
        """Test flexible job scheduling is deferred when there are waiting GPUs to maximize allocation"""
        from dataclasses import asdict
        
        # Set stable time to 10 seconds
        scheduler.config = scheduler.config.from_dict({
            **scheduler.config.to_dict(),
            'worker': {
                **asdict(scheduler.config.worker),
                'gpu_stable_time': 10
            }
        })
        
        # Register node with 2 GPUs
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        
        # 1 GPU is free and stable, 1 is free but stabilizing (waiting)
        stats = [
            GPUStats(0, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1 * 1024**3, 16 * 1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)
        
        node = node_manager.get_node("gpu1")
        # Stable
        node.gpus[0].stable_since = datetime.now() - timedelta(seconds=20)
        # Stabilizing
        node.gpus[1].stable_since = datetime.now() - timedelta(seconds=2)
        node_manager.save_node(node)
        
        # Submit flexible job on gpu1
        # Node has z=1 free stable, k=1 waiting
        # Flexible allocation maps to list max_z=1, max_zk=2. 1 != 2, so should defer
        job = job_manager.submit_job(
            command=["/script.py"],
            requirements="gpu1",
            name="test-job"
        )
        
        scheduler.schedule_cycle()
        
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.PENDING

