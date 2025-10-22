"""End-to-end tests for complete workflow"""
import pytest
import time
from datetime import datetime, timedelta

from scheduler.core.models import JobStatus


class TestFullWorkflow:
    """End-to-end workflow tests

    Note: These tests simulate a full workflow but don't actually
    run subprocesses or connect to real nodes. For true E2E testing,
    you would need to start actual head and worker processes.
    """

    def test_simple_job_workflow(self, full_system):
        """Test simple end-to-end job workflow"""
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
        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Step 3: User submits job
        job = job_manager.submit_job(
            script="/path/to/train.py",
            requirements="2",
            name="training-job",
            script_args=["--epochs", "100"]
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

        # Step 6: GPUs released
        node_manager.release_gpus_from_job("gpu1", job.assigned_gpus)

        node = node_manager.get_node("gpu1")
        assert all(gpu.assigned_job_id is None for gpu in node.gpus[:2])

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

            stable_time = datetime.now() - timedelta(seconds=70)
            node = node_manager.get_node(node_name)
            for gpu in node.gpus:
                gpu.stable_since = stable_time

        # Submit multiple jobs
        jobs = []
        for i in range(5):
            job = job_manager.submit_job(
                script=f"/job{i}.py",
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

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule job
        job = job_manager.submit_job("/script.py", "2")
        scheduler.schedule_cycle()

        # Simulate job failure
        job_manager.fail_job(
            job.job_id,
            exit_code=1,
            error_message="CUDA out of memory"
        )

        # Check state
        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.FAILED
        assert job.exit_code == 1
        assert "CUDA out of memory" in job.error_message

        # Resources should be released
        node_manager.release_gpus_from_job("gpu1", [0, 1])
        node = node_manager.get_node("gpu1")
        assert all(gpu.assigned_job_id is None for gpu in node.gpus)

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

        stable_time = datetime.now() - timedelta(seconds=70)
        node = node_manager.get_node("gpu1")
        for gpu in node.gpus:
            gpu.stable_since = stable_time

        # Submit and schedule job
        job = job_manager.submit_job("/long_running.py", "2")
        scheduler.schedule_cycle()

        assert job_manager.get_job(job.job_id).status == JobStatus.RUNNING

        # Cancel the job
        job_manager.cancel_job(job.job_id)

        job = job_manager.get_job(job.job_id)
        assert job.status == JobStatus.CANCELLED

        # Resources released
        node_manager.release_gpus_from_job("gpu1", [0, 1])


@pytest.fixture
def full_system(temp_dir):
    """Create a complete system for E2E testing"""
    from scheduler.core.config import Config
    from scheduler.head.job_manager import JobManager
    from scheduler.head.node_manager import NodeManager
    from scheduler.head.scheduler import Scheduler
    from scheduler.head.persistence import PersistenceManager

    config = Config(
        temp_dir=temp_dir,
        log_dir=temp_dir,
        gpu_util_threshold=10.0,
        gpu_mem_threshold=10.0,
        gpu_stable_time=60,
        job_startup_grace=30
    )

    persistence = PersistenceManager(storage_dir=temp_dir)
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
