"""True end-to-end tests with actual processes

This module implements true E2E tests where:
- Actual head and worker processes are started
- HTTP communication happens over real network
- Jobs are executed as real subprocesses
- Tests verify complete system integration
"""

import pytest
import multiprocessing
import time
import tempfile
import os
import subprocess
from pathlib import Path
import signal

from scheduler.core.models import JobStatus
from scheduler.core.config import Config, HeadConfig, WorkerConfig, StorageConfig
from scheduler.api import SchedulerClient


def _run_head_process(port, temp_dir, ready_event):
    """Run head node in a separate process"""
    try:
        # Setup logging for head process
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format='[HEAD] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        from scheduler.head.orchestrator import Orchestrator

        # Create config for head node
        config = Config(
            head=HeadConfig(
                port=port,
                heartbeat_timeout=30,
                scheduling_interval=2
            ),
            storage=StorageConfig(
                backend='file',
                data_dir=os.path.join(temp_dir, 'head_data')
            )
        )

        # Create and start orchestrator
        orchestrator = Orchestrator(config)
        orchestrator.start()

        # Signal that head is ready
        ready_event.set()

        # Keep running
        while orchestrator.running:
            time.sleep(0.5)

    except Exception as e:
        import logging
        logging.error(f"Head process error: {e}", exc_info=True)
        ready_event.set()  # Unblock parent even if failed


def _run_worker_process(head_address, node_name, num_gpus, temp_dir, ready_event):
    """Run worker node in a separate process"""
    try:
        # Setup logging for worker process
        import logging
        logging.basicConfig(
            level=logging.INFO,
            format=f'[WORKER-{node_name}] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        from scheduler.worker.daemon import WorkerDaemon

        # Create config for worker
        config = Config(
            address=head_address,
            worker=WorkerConfig(
                temp_dir=os.path.join(temp_dir, f'worker_{node_name}'),
                log_dir=os.path.join(temp_dir, f'logs_{node_name}'),
                work_dir=os.path.join(temp_dir, f'work_{node_name}'),
                gpu_poll_interval=5,
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0,
                gpu_stable_time=5,  # Short for faster tests
                job_startup_grace=5  # Short for faster tests
            )
        )

        # Create and start worker daemon
        daemon = WorkerDaemon(config, node_name, num_gpus)
        daemon.start()

        # Signal that worker is ready
        ready_event.set()

        # Keep running
        while daemon.running:
            time.sleep(0.5)

    except Exception as e:
        import logging
        logging.error(f"Worker process error: {e}", exc_info=True)
        ready_event.set()  # Unblock parent even if failed


@pytest.fixture(scope="module")
def temp_cluster_dir():
    """Create a temporary directory for the cluster"""
    with tempfile.TemporaryDirectory(prefix="scheduler_e2e_") as temp_dir:
        yield temp_dir


@pytest.fixture(scope="module")
def running_cluster(temp_cluster_dir):
    """Start actual head and worker processes for testing

    This fixture:
    1. Starts a head node on a random available port
    2. Starts 2 worker nodes with 2 GPUs each (mocked)
    3. Waits for all processes to be ready
    4. Yields connection info
    5. Cleans up all processes on teardown
    """
    # Find an available port
    import socket
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    head_address = f"localhost:{port}"

    # Events to track when processes are ready
    head_ready = multiprocessing.Event()
    worker1_ready = multiprocessing.Event()
    worker2_ready = multiprocessing.Event()

    # Start head process
    head_proc = multiprocessing.Process(
        target=_run_head_process,
        args=(port, temp_cluster_dir, head_ready),
        name="head-process"
    )
    head_proc.start()

    # Wait for head to be ready (with timeout)
    if not head_ready.wait(timeout=10):
        head_proc.terminate()
        head_proc.join(timeout=5)
        pytest.fail("Head node failed to start within 10 seconds")

    # Give API server a moment to fully initialize
    time.sleep(2)

    # Start worker processes
    worker1_proc = multiprocessing.Process(
        target=_run_worker_process,
        args=(head_address, "worker1", 2, temp_cluster_dir, worker1_ready),
        name="worker1-process"
    )
    worker1_proc.start()

    worker2_proc = multiprocessing.Process(
        target=_run_worker_process,
        args=(head_address, "worker2", 2, temp_cluster_dir, worker2_ready),
        name="worker2-process"
    )
    worker2_proc.start()

    # Wait for workers to be ready
    if not worker1_ready.wait(timeout=10):
        worker1_proc.terminate()
        worker2_proc.terminate()
        head_proc.terminate()
        pytest.fail("Worker1 failed to start within 10 seconds")

    if not worker2_ready.wait(timeout=10):
        worker2_proc.terminate()
        worker1_proc.terminate()
        head_proc.terminate()
        pytest.fail("Worker2 failed to start within 10 seconds")

    # Give workers time to register and send first heartbeat
    time.sleep(3)

    cluster_info = {
        'head_address': head_address,
        'port': port,
        'temp_dir': temp_cluster_dir,
        'processes': {
            'head': head_proc,
            'worker1': worker1_proc,
            'worker2': worker2_proc
        }
    }

    yield cluster_info

    # Cleanup: terminate all processes
    print("\n[CLEANUP] Stopping cluster processes...")

    for name, proc in cluster_info['processes'].items():
        if proc.is_alive():
            print(f"[CLEANUP] Terminating {name}...")
            proc.terminate()
            proc.join(timeout=5)

            if proc.is_alive():
                print(f"[CLEANUP] Force killing {name}...")
                proc.kill()
                proc.join()

    print("[CLEANUP] All processes stopped")


class TestRealProcesses:
    """Test suite for true E2E tests with real processes"""

    def test_cluster_startup(self, running_cluster):
        """Test that head and workers start successfully"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Verify head is responding
        try:
            nodes = client.list_nodes()
            assert len(nodes) == 2, f"Expected 2 workers, got {len(nodes)}"

            node_names = {node.node_name for node in nodes}
            assert "worker1" in node_names
            assert "worker2" in node_names

            # Check that nodes have GPUs
            for node in nodes:
                assert node.num_gpus == 2, f"Node {node.node_name} should have 2 GPUs"

        except Exception as e:
            pytest.fail(f"Failed to connect to cluster: {e}")

    def test_simple_job_submission(self, running_cluster, temp_cluster_dir):
        """Test submitting and running a simple job"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create a simple test script
        script_path = os.path.join(temp_cluster_dir, "test_job.py")
        with open(script_path, 'w') as f:
            f.write("import os\n")
            f.write("print('Job is running!')\n")
            f.write("print(f'CUDA_VISIBLE_DEVICES={os.environ.get(\"CUDA_VISIBLE_DEVICES\", \"not set\")}')\n")
            f.write("import time\n")
            f.write("time.sleep(1)\n")
            f.write("print('Job completed successfully')\n")

        # Submit job
        job = client.submit_job(
            script=script_path,
            requirements="1",
            name="test-simple-job"
        )

        assert job.job_id is not None
        assert job.status == JobStatus.PENDING

        # Wait for job to complete
        max_wait = 30
        for i in range(max_wait):
            job = client.get_job(job.job_id)
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                break
            time.sleep(1)

        # Check final status
        assert job.status == JobStatus.COMPLETED, f"Job status is {job.status}, error: {job.error_message}"
        assert job.assigned_node in ["worker1", "worker2"]
        assert len(job.assigned_gpus) == 1

    def test_multiple_jobs_sequential(self, running_cluster, temp_cluster_dir):
        """Test running multiple jobs sequentially"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create test scripts
        job_ids = []

        for i in range(3):
            script_path = os.path.join(temp_cluster_dir, f"job_{i}.py")
            with open(script_path, 'w') as f:
                f.write(f"print('Job {i} running')\n")
                f.write("import time\n")
                f.write("time.sleep(0.5)\n")
                f.write(f"print('Job {i} done')\n")

            job = client.submit_job(
                script=script_path,
                requirements="1",
                name=f"job-{i}"
            )
            job_ids.append(job.job_id)

        # Wait for all jobs to complete
        max_wait = 45
        for i in range(max_wait):
            jobs = [client.get_job(jid) for jid in job_ids]
            if all(j.status == JobStatus.COMPLETED for j in jobs):
                break
            time.sleep(1)

        # Verify all completed
        jobs = [client.get_job(jid) for jid in job_ids]
        for i, job in enumerate(jobs):
            assert job.status == JobStatus.COMPLETED, f"Job {i} status is {job.status}"

    def test_concurrent_jobs(self, running_cluster, temp_cluster_dir):
        """Test running jobs concurrently on different workers"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create 4 test scripts (we have 4 GPUs total: 2 per worker)
        job_ids = []

        for i in range(4):
            script_path = os.path.join(temp_cluster_dir, f"concurrent_{i}.py")
            with open(script_path, 'w') as f:
                f.write(f"print('Concurrent job {i} starting')\n")
                f.write("import time\n")
                f.write("time.sleep(2)\n")
                f.write(f"print('Concurrent job {i} finished')\n")

            job = client.submit_job(
                script=script_path,
                requirements="1",
                name=f"concurrent-{i}"
            )
            job_ids.append(job.job_id)

        # Wait a moment for scheduling
        time.sleep(5)

        # Check that multiple jobs are running concurrently
        jobs = [client.get_job(jid) for jid in job_ids]
        running_count = sum(1 for j in jobs if j.status == JobStatus.RUNNING)

        assert running_count >= 2, f"Expected at least 2 jobs running concurrently, got {running_count}"

        # Wait for all to complete
        max_wait = 60
        for i in range(max_wait):
            jobs = [client.get_job(jid) for jid in job_ids]
            if all(j.status == JobStatus.COMPLETED for j in jobs):
                break
            time.sleep(1)

        # Verify all completed
        jobs = [client.get_job(jid) for jid in job_ids]
        for i, job in enumerate(jobs):
            assert job.status == JobStatus.COMPLETED, f"Concurrent job {i} status is {job.status}"

    def test_job_cancellation(self, running_cluster, temp_cluster_dir):
        """Test canceling a running job"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create a long-running job
        script_path = os.path.join(temp_cluster_dir, "long_job.py")
        with open(script_path, 'w') as f:
            f.write("import time\n")
            f.write("print('Long job started')\n")
            f.write("for i in range(100):\n")
            f.write("    time.sleep(1)\n")
            f.write("    print(f'Iteration {i}')\n")

        # Submit job
        job = client.submit_job(
            script=script_path,
            requirements="1",
            name="long-job"
        )

        # Wait for it to start running
        max_wait = 20
        for i in range(max_wait):
            job = client.get_job(job.job_id)
            if job.status == JobStatus.RUNNING:
                break
            time.sleep(1)

        assert job.status == JobStatus.RUNNING, "Job should be running"

        # Cancel the job
        client.cancel_job(job.job_id)

        # Wait for cancellation to take effect
        time.sleep(3)

        # Check that job was cancelled
        job = client.get_job(job.job_id)
        assert job.status == JobStatus.CANCELLED, f"Job should be cancelled, got {job.status}"

    def test_job_with_dependencies(self, running_cluster, temp_cluster_dir):
        """Test job dependencies"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Job 1: Create a file
        script1_path = os.path.join(temp_cluster_dir, "create_file.py")
        output_file = os.path.join(temp_cluster_dir, "dependency_output.txt")
        with open(script1_path, 'w') as f:
            f.write(f"with open(r'{output_file}', 'w') as f:\n")
            f.write("    f.write('Job 1 completed')\n")
            f.write("print('Job 1 done')\n")

        job1 = client.submit_job(
            script=script1_path,
            requirements="1",
            name="job1-create-file"
        )

        # Job 2: Read the file (depends on job1)
        script2_path = os.path.join(temp_cluster_dir, "read_file.py")
        with open(script2_path, 'w') as f:
            f.write(f"with open(r'{output_file}', 'r') as f:\n")
            f.write("    content = f.read()\n")
            f.write("    print(f'Read: {{content}}')\n")

        job2 = client.submit_job(
            script=script2_path,
            requirements="1",
            name="job2-read-file",
            depends_on=[job1.job_id]
        )

        # Job 2 should start as PENDING (waiting for job1)
        job2_status = client.get_job(job2.job_id)
        assert job2_status.status == JobStatus.PENDING

        # Wait for both to complete
        max_wait = 30
        for i in range(max_wait):
            j1 = client.get_job(job1.job_id)
            j2 = client.get_job(job2.job_id)
            if j1.status == JobStatus.COMPLETED and j2.status == JobStatus.COMPLETED:
                break
            time.sleep(1)

        # Verify both completed
        job1_final = client.get_job(job1.job_id)
        job2_final = client.get_job(job2.job_id)

        assert job1_final.status == JobStatus.COMPLETED
        assert job2_final.status == JobStatus.COMPLETED

        # Verify job2 started after job1 completed
        assert job2_final.start_time > job1_final.end_time, "Job 2 should start after Job 1 completes"

    def test_job_with_environment_variables(self, running_cluster, temp_cluster_dir):
        """Test job with custom environment variables"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create script that reads env vars
        script_path = os.path.join(temp_cluster_dir, "env_test.py")
        with open(script_path, 'w') as f:
            f.write("import os\n")
            f.write("test_var = os.environ.get('TEST_VAR', 'NOT_SET')\n")
            f.write("cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', 'NOT_SET')\n")
            f.write(f"print(f'TEST_VAR={{test_var}}')\n")
            f.write(f"print(f'CUDA_VISIBLE_DEVICES={{cuda_devices}}')\n")
            f.write("assert test_var == 'hello_world', f'Expected hello_world, got {test_var}'\n")

        # Submit job with env vars
        job = client.submit_job(
            script=script_path,
            requirements="1",
            name="env-test",
            env_vars={"TEST_VAR": "hello_world"}
        )

        # Wait for completion
        max_wait = 20
        for i in range(max_wait):
            job = client.get_job(job.job_id)
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                break
            time.sleep(1)

        # Should complete successfully (assertion in script should pass)
        assert job.status == JobStatus.COMPLETED, f"Job failed: {job.error_message}"

    def test_job_failure(self, running_cluster, temp_cluster_dir):
        """Test that failed jobs are properly reported"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create a script that fails
        script_path = os.path.join(temp_cluster_dir, "failing_job.py")
        with open(script_path, 'w') as f:
            f.write("print('About to fail')\n")
            f.write("raise RuntimeError('Intentional failure')\n")

        # Submit job
        job = client.submit_job(
            script=script_path,
            requirements="1",
            name="failing-job"
        )

        # Wait for job to fail
        max_wait = 20
        for i in range(max_wait):
            job = client.get_job(job.job_id)
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
                break
            time.sleep(1)

        # Check that job failed
        assert job.status == JobStatus.FAILED
        assert job.exit_code != 0

    def test_job_logs_retrieval(self, running_cluster, temp_cluster_dir):
        """Test retrieving job logs"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create script with specific output
        script_path = os.path.join(temp_cluster_dir, "log_test.py")
        test_message = "UNIQUE_LOG_MESSAGE_12345"
        with open(script_path, 'w') as f:
            f.write(f"print('{test_message}')\n")
            f.write("import sys\n")
            f.write("print('Error message', file=sys.stderr)\n")

        # Submit and wait for completion
        job = client.submit_job(
            script=script_path,
            requirements="1",
            name="log-test"
        )

        max_wait = 20
        for i in range(max_wait):
            job = client.get_job(job.job_id)
            if job.status == JobStatus.COMPLETED:
                break
            time.sleep(1)

        assert job.status == JobStatus.COMPLETED

        # Retrieve logs
        stdout_logs = client.get_job_logs(job.job_id, stream='stdout')

        # Verify our message is in the logs
        assert test_message in stdout_logs, f"Expected '{test_message}' in logs, got: {stdout_logs}"

    def test_cluster_health_check(self, running_cluster):
        """Test cluster health check endpoint"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Health check should succeed
        is_healthy = client.health_check()
        assert is_healthy, "Cluster should be healthy"

    def test_list_and_filter_jobs(self, running_cluster, temp_cluster_dir):
        """Test listing and filtering jobs"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Submit several jobs with different statuses
        script_path = os.path.join(temp_cluster_dir, "quick_job.py")
        with open(script_path, 'w') as f:
            f.write("print('Quick job')\n")

        job_ids = []
        for i in range(3):
            job = client.submit_job(
                script=script_path,
                requirements="1",
                name=f"list-test-{i}"
            )
            job_ids.append(job.job_id)

        # Wait for them to complete
        time.sleep(10)

        # List all jobs
        all_jobs = client.list_jobs()
        assert len(all_jobs) >= 3, "Should have at least 3 jobs"

        # Filter by status
        completed_jobs = client.list_jobs(status=JobStatus.COMPLETED)
        assert len(completed_jobs) > 0, "Should have some completed jobs"


@pytest.mark.slow
class TestRealProcessesExtended:
    """Extended E2E tests (marked as slow)"""

    def test_worker_reconnection(self, running_cluster):
        """Test worker reconnection after disconnect"""
        # This test would simulate network disconnection
        # and verify worker reconnects properly
        # Implementation would require more sophisticated process control
        pytest.skip("Worker reconnection test requires advanced process control")

    def test_stress_many_jobs(self, running_cluster, temp_cluster_dir):
        """Stress test with many jobs"""
        client = SchedulerClient(address=running_cluster['head_address'])

        # Create script
        script_path = os.path.join(temp_cluster_dir, "stress_job.py")
        with open(script_path, 'w') as f:
            f.write("import time\n")
            f.write("time.sleep(0.5)\n")

        # Submit many jobs
        num_jobs = 20
        job_ids = []
        for i in range(num_jobs):
            job = client.submit_job(
                script=script_path,
                requirements="1",
                name=f"stress-{i}"
            )
            job_ids.append(job.job_id)

        # Wait for all to complete
        max_wait = 120
        for i in range(max_wait):
            jobs = [client.get_job(jid) for jid in job_ids]
            completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
            if completed == num_jobs:
                break
            time.sleep(1)

        # Verify all completed
        jobs = [client.get_job(jid) for jid in job_ids]
        completed = sum(1 for j in jobs if j.status == JobStatus.COMPLETED)
        assert completed == num_jobs, f"Expected {num_jobs} completed, got {completed}"
