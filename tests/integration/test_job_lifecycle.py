"""Integration tests for complete job lifecycle"""
import pytest
from datetime import datetime, timedelta

from scheduler.core.models import (
    Job, Node, GPU, GPUStats, JobRequirement,
    JobStatus, NodeStatus
)
from scheduler.core.config import Config
from scheduler.manager import JobManager
from scheduler.manager import NodeManager
from scheduler.manager import Scheduler
from scheduler.manager import PersistenceManager


@pytest.fixture
def full_system(temp_dir):
    """Create a complete system setup"""
    from scheduler.storage import FileBackend
    from scheduler.core.config import HeadConfig, WorkerConfig

    config = Config(
        head=HeadConfig(heartbeat_timeout=10),
        worker=WorkerConfig(
            temp_dir=temp_dir,
            log_dir=temp_dir,
            work_dir=temp_dir,
            heartbeat_interval=2,  # Must be <= gpu_stable_time
            gpu_poll_interval=2,   # Must be <= gpu_stable_time for validation
            gpu_util_threshold=10.0,
            gpu_mem_threshold=10.0,
            gpu_stable_time=2,  # Reduced from 60 for faster tests
            job_startup_grace=3  # Reduced from 30 for faster tests
        )
    )

    backend = FileBackend(storage_dir=temp_dir)
    persistence = PersistenceManager(backend=backend, config=config)
    job_manager = JobManager(persistence=persistence, config=config)
    node_manager = NodeManager(persistence=persistence, config=config)
    scheduler = Scheduler(job_manager, node_manager, config)

    return {
        'config': config,
        'persistence': persistence,
        'job_manager': job_manager,
        'node_manager': node_manager,
        'scheduler': scheduler
    }


class TestJobLifecycle:
    """Integration tests for job lifecycle"""

    def test_submit_and_schedule_job(self, full_system):
        """Test complete flow: submit job -> register node -> schedule"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Submit a job
        job = job_manager.submit_job(
            command=["/path/to/train.py"],
            requirements="2",
            name="training-job"
        )

        assert job.status == JobStatus.PENDING

        # Register a node
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Send heartbeat with free GPUs
        stats = []
        stable_time = datetime.now() - timedelta(seconds=3)
        for i in range(4):
            stats.append(GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300))

        node_manager.update_heartbeat("gpu1", stats)

        # Manually set stability for testing
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Run scheduling
        scheduler.schedule_cycle()

        # Check job was scheduled
        updated_job = job_manager.get_job(job.job_id)
        assert updated_job.status == JobStatus.RUNNING
        assert updated_job.assigned_node == "gpu1"
        assert len(updated_job.assigned_gpus) == 2

        # Verify the job got the suggested GPUs via assigned_gpus
        # (these will be passed as CUDA_VISIBLE_DEVICES)
        assert updated_job.assigned_gpus is not None
        assert len(updated_job.assigned_gpus) == 2

    def test_job_completion_frees_resources(self, full_system):
        """Test that completing a job allows GPUs to become available via monitoring"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup node
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule job
        job = job_manager.submit_job("/script.py", "2")
        scheduler.schedule_cycle()

        # Verify job is running
        assert job_manager.get_job(job.job_id).status == JobStatus.RUNNING

        # Simulate job running - GPUs show high usage
        high_usage_stats = [
            GPUStats(0, 85.0, 14*1024**3, 16*1024**3, 72, 280, 300),
            GPUStats(1, 85.0, 14*1024**3, 16*1024**3, 72, 280, 300)
        ]
        node_manager.update_heartbeat("gpu1", high_usage_stats)

        # Complete the job
        job_manager.complete_job(job.job_id, exit_code=0)

        # Simulate GPU usage dropping after job completes (detected by monitoring)
        low_usage_stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", low_usage_stats)

        # GPUs should start becoming stable again
        node = node_manager.get_node("gpu1")
        assert all(gpu.stable_since is not None for gpu in node.gpus)

    def test_multiple_jobs_scheduling(self, full_system):
        """Test scheduling multiple jobs across different nodes"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Register two nodes
        for node_name in ["gpu1", "gpu2"]:
            node_manager.register_node(node_name, f"192.168.1.{10 if node_name == 'gpu1' else 11}", 2)

            stats = [
                GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
                GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
            ]
            node_manager.update_heartbeat(node_name, stats)

            stable_time = datetime.now() - timedelta(seconds=3)
            node = node_manager.get_node(node_name)
            for gpu in node.gpus:
                gpu.stable_since = stable_time

        # Submit multiple jobs
        job1 = job_manager.submit_job("/script1.py", "2", priority=1)
        job2 = job_manager.submit_job("/script2.py", "2", priority=2)
        job3 = job_manager.submit_job("/script3.py", "2", priority=3)

        # Run scheduling
        scheduler.schedule_cycle()

        # Check that 2 jobs were scheduled (we have 2 nodes with 2 GPUs each)
        running_jobs = job_manager.get_running_jobs()
        assert len(running_jobs) == 2

        # Highest priority jobs should be running
        running_ids = [j.job_id for j in running_jobs]
        assert job2.job_id in running_ids or job3.job_id in running_ids

    def test_dependency_chain_execution(self, full_system):
        """Test jobs with dependencies execute in order"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup node
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit jobs with dependencies
        job1 = job_manager.submit_job("/preprocess.py", "1", name="preprocess")
        job2 = job_manager.submit_job(
            "/train.py", "1",
            name="train",
            dependencies=[job1.job_id]
        )

        # First scheduling cycle - only job1 should run
        scheduler.schedule_cycle()

        assert job_manager.get_job(job1.job_id).status == JobStatus.RUNNING
        assert job_manager.get_job(job2.job_id).status == JobStatus.PENDING

        # Complete job1
        job_manager.complete_job(job1.job_id, exit_code=0)

        # Simulate GPU becoming free after job1 completes (detected by monitoring)
        # Reset GPU stability and clear grace period
        node = node_manager.get_node("gpu1")
        low_usage_stats = GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        node.gpus[0].update_stats(low_usage_stats, util_threshold=10.0, mem_threshold=10.0)
        node.gpus[0].stable_since = stable_time
        node.grace_period_until = None  # Clear grace period

        # Second scheduling cycle - job2 should run now
        scheduler.schedule_cycle()

        assert job_manager.get_job(job2.job_id).status == JobStatus.RUNNING

    def test_grace_period_prevents_scheduling(self, full_system):
        """Test that grace period prevents new jobs from being scheduled"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup node
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule first job
        job1 = job_manager.submit_job("/script1.py", "1")
        scheduler.schedule_cycle()

        # Node should be in grace period
        node = node_manager.get_node("gpu1")
        assert node.is_in_grace_period() is True

        # Submit second job
        job2 = job_manager.submit_job("/script2.py", "1")

        # Try to schedule - should not schedule due to grace period
        scheduler.schedule_cycle()

        assert job_manager.get_job(job2.job_id).status == JobStatus.PENDING

    def test_node_disconnection_handling(self, full_system):
        """Test handling of node disconnection"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']

        # Register node and send heartbeat
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        node = node_manager.get_node("gpu1")
        assert node.status == NodeStatus.CONNECTED

        # Simulate time passing (node disconnects)
        node.last_heartbeat = datetime.now() - timedelta(seconds=100)

        # Check timeouts
        node_manager.check_timeouts()

        node = node_manager.get_node("gpu1")
        assert node.status == NodeStatus.DISCONNECTED

    def test_persistence_across_restart(self, temp_dir):
        """Test that state is preserved across restarts"""
        from scheduler.storage import FileBackend
        from scheduler.core.config import WorkerConfig

        config = Config(worker=WorkerConfig(temp_dir=temp_dir, log_dir=temp_dir, work_dir=temp_dir))

        # First instance - submit job and register node
        backend1 = FileBackend(storage_dir=temp_dir)
        persistence1 = PersistenceManager(backend=backend1, config=config)
        job_manager1 = JobManager(persistence=persistence1, config=config)
        node_manager1 = NodeManager(persistence=persistence1, config=config)

        job = job_manager1.submit_job("/script.py", "2", name="persistent-job")
        node_manager1.register_node("gpu1", "192.168.1.10", 4)

        job_id = job.job_id

        # Second instance - simulate restart
        backend2 = FileBackend(storage_dir=temp_dir)
        persistence2 = PersistenceManager(backend=backend2, config=config)
        job_manager2 = JobManager(persistence=persistence2, config=config)
        node_manager2 = NodeManager(persistence=persistence2, config=config)

        # State should be loaded
        loaded_job = job_manager2.get_job(job_id)
        loaded_node = node_manager2.get_node("gpu1")

        assert loaded_job.name == "persistent-job"
        assert loaded_node.num_gpus == 4

    def test_high_priority_job_preemption_simulation(self, full_system):
        """Test that high priority jobs are scheduled before low priority"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup node
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [
            GPUStats(0, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300),
            GPUStats(1, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300)
        ]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit low priority job first, then high priority
        low_job = job_manager.submit_job("/low.py", "2", priority=1)
        high_job = job_manager.submit_job("/high.py", "2", priority=100)

        # Schedule - high priority should be scheduled
        scheduler.schedule_cycle()

        assert job_manager.get_job(high_job.job_id).status == JobStatus.RUNNING
        assert job_manager.get_job(low_job.job_id).status == JobStatus.PENDING
