"""Integration tests for complete scheduler workflow (simulated E2E)

These tests simulate a full workflow by wiring in-memory managers together.
They do not start real processes or perform real HTTP calls.
"""
import pytest
import time
from datetime import datetime, timedelta

from scheduler.core.models import JobStatus


class TestFullWorkflow:
    """Integration workflow tests (simulated E2E)

    Note: These tests simulate a full workflow but don't actually
    run subprocesses or connect to real nodes. For true end-to-end testing,
    start actual head and worker processes (see tests in tests/e2e/).
    """

    def test_simple_job_workflow(self, full_system):
        """Test simple job workflow across components"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Step 1: Worker registers
        node_manager.register_node("gpu1", "192.168.1.10", 4)

        # Step 2: Worker sends heartbeat
        from scheduler.core.models import GPUStats
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", stats)

        # Set GPUs as stable (simulate time passing)
        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Step 3: User submits job
        job = job_manager.submit_job(
            command=["/path/to/train.py"],
            requirements="2",
            name="training-job"
        )

        assert job.status == JobStatus.PENDING

        # Step 4: Scheduler assigns job
        scheduler.schedule_cycle()

        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.RUNNING
        assert job.assigned_node == "gpu1"
        assert len(job.assigned_gpus) == 2

        # Step 5: Simulate job completion
        job_manager.complete_job(job.job_id, exit_code=0)

        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.COMPLETED
        assert job.exit_code == 0

        # Step 6: Simulate GPU usage dropping after job completion (detected by monitoring)
        # GPUs become available naturally when actual usage drops
        from scheduler.core.models import GPUStats
        low_usage_stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(4)]
        node_manager.update_heartbeat("gpu1", low_usage_stats)

        node = node_manager.get_node("gpu1")
        # GPUs should start becoming stable again after low usage is detected
        assert all(gpu.stable_since is not None for gpu in node.gpus[:2])

    def test_multi_job_multi_node_workflow(self, full_system):
        """Test workflow with multiple jobs and nodes"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Register multiple nodes
        from scheduler.core.models import GPUStats

        for i, node_name in enumerate(["gpu1", "gpu2", "gpu3"]):
            node_manager.register_node(node_name, f"192.168.1.{10+i}", 4)

            stats = [GPUStats(j, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for j in range(4)]
            node_manager.update_heartbeat(node_name, stats)

            stable_time = datetime.now() - timedelta(seconds=3)
            node = node_manager.get_node(node_name)
            for gpu in node.gpus:
                gpu.stable_since = stable_time

        # Submit multiple jobs
        jobs = []
        for i in range(5):
            job = job_manager.submit_job(
                command=[f"/job{i}.py"],
                requirements="2",
                name=f"job-{i}",
                priority=i
            )
            jobs.append(job)

        # Run scheduler
        scheduler.schedule_cycle()

        # Check that jobs are scheduled
        running = job_manager.get_running_jobs()
        # We have 3 nodes * 4 GPUs = 12 GPUs total
        # Each job needs 2 GPUs, so 6 jobs can run
        # But we only have 5 jobs
        assert len(running) >= 3  # At least 3 should be running

    def test_job_failure_workflow(self, full_system):
        """Test workflow when job fails"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup
        from scheduler.core.models import GPUStats
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(2)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule job
        job = job_manager.submit_job(["/script.py"], "2")
        scheduler.schedule_cycle()

        # Simulate job failure
        job_manager.fail_job(
            job.job_id,
            error_message="CUDA out of memory"
        )

        # Check state
        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.FAILED
        assert "CUDA out of memory" in job.error_message

        # Simulate GPU usage dropping after job fails (detected by monitoring)
        from scheduler.core.models import GPUStats
        low_usage_stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(2)]
        node_manager.update_heartbeat("gpu1", low_usage_stats)

        # GPUs become available naturally when actual usage drops
        node = node_manager.get_node("gpu1")
        assert all(gpu.stable_since is not None for gpu in node.gpus)

    def test_job_cancellation_workflow(self, full_system):
        """Test canceling a job"""
        job_manager = full_system['job_manager']
        node_manager = full_system['node_manager']
        scheduler = full_system['scheduler']

        # Setup
        from scheduler.core.models import GPUStats
        node_manager.register_node("gpu1", "192.168.1.10", 2)
        stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(2)]
        node_manager.update_heartbeat("gpu1", stats)

        stable_time = datetime.now() - timedelta(seconds=3)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule job
        job = job_manager.submit_job(["/long_running.py"], "2")
        scheduler.schedule_cycle()

        assert job_manager.get_job(job.job_id).status == JobStatus.RUNNING

        # Cancel the job
        job_manager.cancel_job(job.job_id)

        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.CANCELLED

        # Simulate GPU usage dropping after job is cancelled (detected by monitoring)
        from scheduler.core.models import GPUStats
        low_usage_stats = [GPUStats(i, 5.0, 1*1024**3, 16*1024**3, 45, 50, 300) for i in range(2)]
        node_manager.update_heartbeat("gpu1", low_usage_stats)

        # GPUs become available naturally when actual usage drops
        node = node_manager.get_node("gpu1")
        assert all(gpu.stable_since is not None for gpu in node.gpus)


@pytest.fixture
def full_system(temp_dir):
    """Create a complete system for integration testing"""
    from scheduler.core.config import Config
    from scheduler.manager import JobManager
    from scheduler.manager import NodeManager
    from scheduler.manager import Scheduler
    from scheduler.manager import PersistenceManager
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


