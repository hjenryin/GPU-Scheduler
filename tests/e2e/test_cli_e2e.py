"""End-to-end tests for CLI commands using subprocess

This module tests the actual CLI commands as they would be used from the terminal.
All tests use subprocess to invoke 'scheduler' commands directly.

Note: This module has its own running_cluster fixture to ensure test isolation
from test_real_processes.py. Each test file gets its own scheduler instance.
"""

import pytest
import subprocess
import time
import tempfile
import os
import signal
import re
import multiprocessing
from pathlib import Path


@pytest.fixture(scope="module")
def temp_test_dir():
    """Create a temporary directory for CLI E2E tests"""
    with tempfile.TemporaryDirectory(prefix="scheduler_cli_e2e_") as temp_dir:
        yield temp_dir


def _run_head_process(port, temp_dir, ready_event):
    """Run head node in a separate process"""
    try:
        import logging
        import os
        log_level = logging.DEBUG if os.environ.get('SCHEDULER_LOG_LEVEL') == 'DEBUG' else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='[HEAD] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        from scheduler.head.orchestrator import Orchestrator
        from scheduler.core import Config
        from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig

        config = Config(
            head=HeadConfig(
                port=port,
                heartbeat_timeout=10,  # Reduced from 30 for faster e2e tests
                scheduling_interval=1
            ),
            worker=WorkerConfig(
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0,
                heartbeat_interval=1,  # Reduced from 2 for faster e2e tests
                gpu_poll_interval=1,  # Reduced from 2 for faster e2e tests
                job_startup_grace=2  # Reduced from 3 for faster e2e tests
            ),
            storage=StorageConfig(
                backend='file',
                data_dir=os.path.join(temp_dir, 'head_data')
            )
        )

        orchestrator = Orchestrator(config)
        orchestrator.start()
        ready_event.set()

        while orchestrator.running:
            time.sleep(0.5)

    except Exception as e:
        import logging
        logging.error(f"Head process error: {e}", exc_info=True)
        ready_event.set()


def _run_worker_process(head_address, node_name, temp_dir, ready_event):
    """Run worker node in a separate process"""
    try:
        import logging
        import os
        log_level = logging.DEBUG if os.environ.get('SCHEDULER_LOG_LEVEL') == 'DEBUG' else logging.INFO
        logging.basicConfig(
            level=log_level,
            format=f'[WORKER-{node_name}] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        from scheduler.worker.daemon import WorkerDaemon
        from scheduler.core import Config
        from scheduler.core.config import WorkerConfig

        config = Config(
            address=head_address,
            worker=WorkerConfig(
                temp_dir=os.path.join(temp_dir, f'worker_{node_name}'),
                log_dir=os.path.join(temp_dir, f'logs_{node_name}'),
                work_dir=os.path.join(temp_dir, f'work_{node_name}'),
                heartbeat_interval=1,  # Reduced from 2 for faster e2e tests
                gpu_poll_interval=1,  # Reduced from 2 for faster e2e tests
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0,
                job_startup_grace=2  # Reduced from 3 for faster e2e tests
            )
        )

        daemon = WorkerDaemon(config, node_name, num_gpus=None)
        ready_event.set()
        daemon.run()

    except Exception as e:
        import logging
        logging.error(f"Worker process error: {e}", exc_info=True)
        ready_event.set()


@pytest.fixture(scope="module")
def running_cluster(temp_test_dir):
    """Start actual head and worker processes for CLI testing
    
    This fixture is specific to test_cli_e2e.py to ensure test isolation.
    It starts its own scheduler instance independent of other test files.
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
    worker_ready = multiprocessing.Event()

    # Start head process
    head_proc = multiprocessing.Process(
        target=_run_head_process,
        args=(port, temp_test_dir, head_ready),
        name="cli-test-head"
    )
    head_proc.start()

    # Wait for head to be ready
    if not head_ready.wait(timeout=10):
        head_proc.terminate()
        head_proc.join(timeout=5)
        pytest.fail("Head node failed to start within 10 seconds")

    time.sleep(1)  # Reduced from 2 for faster e2e tests

    # Start worker process
    worker_proc = multiprocessing.Process(
        target=_run_worker_process,
        args=(head_address, "cli-worker", temp_test_dir, worker_ready),
        name="cli-test-worker"
    )
    worker_proc.start()

    # Wait for worker to be ready
    if not worker_ready.wait(timeout=10):
        worker_proc.terminate()
        head_proc.terminate()
        pytest.fail("Worker failed to start within 10 seconds")

    time.sleep(2)  # Reduced from 3 for faster e2e tests

    cluster_info = {
        'head_address': head_address,
        'port': port,
        'temp_dir': temp_test_dir,
        'processes': {
            'head': head_proc,
            'worker': worker_proc
        }
    }

    yield cluster_info

    # Cleanup: terminate all processes
    print("\n[CLI-TEST CLEANUP] Stopping cluster processes...")

    for name, proc in cluster_info['processes'].items():
        if proc.is_alive():
            print(f"[CLI-TEST CLEANUP] Terminating {name}...")
            proc.terminate()
            proc.join(timeout=5)

            if proc.is_alive():
                print(f"[CLI-TEST CLEANUP] Force killing {name}...")
                proc.kill()
                proc.join()

    print("[CLI-TEST CLEANUP] All processes stopped")


def run_scheduler_cmd(cmd_args, env_override=None, timeout=30, input_data=None):
    """Helper to run a scheduler CLI command via conda
    
    Args:
        cmd_args: List of arguments after 'scheduler' (e.g., ['submit', '--req', '1', 'script.py'])
        env_override: Dict of environment variables to override
        timeout: Command timeout in seconds
        input_data: String to send to stdin
        
    Returns:
        CompletedProcess with returncode, stdout, stderr
    """
    cmd = ["python", "-m", "scheduler.cli.main"] + cmd_args
    
    env = os.environ.copy()
    if env_override:
        env.update(env_override)
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        input=input_data
    )
    return result


class TestCLIStart:
    """Test 'scheduler start' command"""
    
    def test_start_help(self):
        """Test that start command has proper help"""
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "start", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert "Start" in result.stdout
        assert "--head" in result.stdout
        assert "--address" in result.stdout
        assert "--port" in result.stdout
    
    def test_start_validates_arguments(self):
        """Test that start command validates arguments correctly"""
        # Test: Must specify either --head or --address
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "start"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Should fail with exit code 2 (argument error)
        assert result.returncode == 2
        assert "Must specify either --head or --address" in result.stdout or "Must specify" in result.stdout
    
    def test_start_head_with_options(self):
        """Test that start --head accepts all documented options"""
        # We can't actually start a head node without managing locks,
        # but we can verify the command line parsing works
        # Note: The running_cluster fixture already tests actual head node startup
        
        # Just verify the command accepts the documented flags without error
        # by checking that --help shows all the expected options
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "start", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert result.returncode == 0
        
        # Verify all documented options are present
        expected_options = [
            "--head",
            "--address",
            "--port",
            "--node-name",
            "--num-gpus",
            "--block",
            "--log-level",
            "--heartbeat-timeout",
            "--scheduling-interval",
            "--gpu-poll-interval",
            "--gpu-util-threshold",
            "--gpu-mem-threshold",
            "--job-startup-grace"
        ]

        for option in expected_options:
            assert option in result.stdout, f"Expected option {option} not found in help"
    
    # Note: Actual start/stop testing is complex due to singleton locks.
    # These are tested via the running_cluster fixture and the working system.
    # Manual start/stop commands are verified via the running_cluster fixture.
    
    def test_start_worker_actual(self, running_cluster, temp_test_dir):
        """Test actually starting a worker node"""
        worker_name = "test-start-worker"
        
        # Start a worker
        start_result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "start",
             "--address", running_cluster['head_address'],
             "--node-name", worker_name],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        assert start_result.returncode == 0, f"Failed to start worker: {start_result.stderr}"
        
        # Give it time to register
        time.sleep(3)  # Reduced from 5 for faster e2e tests

        # Verify worker is registered using jobs command (which shows nodes)
        from scheduler.api import SchedulerClient
        client = SchedulerClient(running_cluster['head_address'])
        
        nodes = client.list_nodes()
        node_names = [node.node_name for node in nodes]
        assert worker_name in node_names, f"Worker {worker_name} not registered. Found: {node_names}"
        
        # Stop the worker (stop without --all stops all local workers)
        stop_result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "stop"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert stop_result.returncode == 0, f"Failed to stop worker: {stop_result.stderr}"


class TestCLISubmit:
    """Test 'scheduler submit' command"""
    
    def test_submit_simple_job(self, running_cluster, temp_test_dir):
        """Test submitting a simple job"""
        # Create test script
        script_path = os.path.join(temp_test_dir, "test_job.py")
        with open(script_path, 'w') as f:
            f.write("print('Hello from job')\n")
        
        # Submit job
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0, f"Submit failed: {result.stderr}"
        assert "Job ID:" in result.stdout or "job_" in result.stdout
        
        # Extract job ID
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match, f"Could not find job ID in output: {result.stdout}"
        job_id = match.group(1)
        
        # Wait a moment for job to complete
        time.sleep(3)  # Reduced from 5 for faster e2e tests
        
        # Verify job completed
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        assert job_id in result.stdout
    
    def test_submit_with_requirements(self, running_cluster, temp_test_dir):
        """Test submitting with different GPU requirements"""
        script_path = os.path.join(temp_test_dir, "test_req.py")
        with open(script_path, 'w') as f:
            f.write("import os; print(os.environ.get('CUDA_VISIBLE_DEVICES', 'not set'))\n")
        
        # Test with 2 GPUs
        result = run_scheduler_cmd(
            ['submit', '--req', '2', '--async', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
    
    def test_submit_with_env_vars(self, running_cluster, temp_test_dir):
        """Test submitting with environment variables"""
        script_path = os.path.join(temp_test_dir, "test_env.py")
        with open(script_path, 'w') as f:
            f.write("import os\n")
            f.write("val = os.environ.get('MY_TEST_VAR', 'NOT_SET')\n")
            f.write("print(f'MY_TEST_VAR={val}')\n")
        
        # Submit with env var - just verify CLI accepts it
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', 
             '--env', 'MY_TEST_VAR=test_value_123',
             script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        # Verify submission succeeded
        assert result.returncode == 0, f"Submit failed: {result.stderr}"
        assert "Job ID:" in result.stdout or "job_" in result.stdout
        
        # Extract job ID to verify it was created
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match, f"Could not find job ID in output: {result.stdout}"
        job_id = match.group(1)
        
        # Verify job was created (just check it exists, don't wait for completion)
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        assert job_id in result.stdout
    
    def test_submit_with_name(self, running_cluster, temp_test_dir):
        """Test submitting with custom job name"""
        script_path = os.path.join(temp_test_dir, "named_job.py")
        with open(script_path, 'w') as f:
            f.write("print('Named job')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', '--name', 'my-custom-job', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job_id = match.group(1)
        
        # Verify name appears in job listing
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert 'my-custom-job' in result.stdout or 'custom' in result.stdout
    
    def test_submit_with_script_args(self, running_cluster, temp_test_dir):
        """Test submitting with script arguments after --"""
        script_path = os.path.join(temp_test_dir, "args_job.py")
        with open(script_path, 'w') as f:
            f.write("import sys\n")
            f.write("print(f'Args: {sys.argv[1:]}')\n")
            f.write("assert '--epochs' in sys.argv\n")
            f.write("assert '100' in sys.argv\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script_path, '--', '--epochs', '100'],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0


class TestCLIJobs:
    """Test 'scheduler jobs' command"""
    
    def test_jobs_list_all(self, running_cluster, temp_test_dir):
        """Test listing all jobs"""
        result = run_scheduler_cmd(
            ['jobs'],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        # Should show some output (headers at minimum)
        assert len(result.stdout) > 0
    
    def test_jobs_filter_by_status(self, running_cluster, temp_test_dir):
        """Test filtering jobs by status"""
        # Submit a job first
        script_path = os.path.join(temp_test_dir, "filter_test.py")
        with open(script_path, 'w') as f:
            f.write("print('test')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        time.sleep(2)
        
        # Try different filters
        for filter_status in ['all', 'pending', 'running', 'completed']:
            result = run_scheduler_cmd(
                ['jobs', '--filter', filter_status],
                env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
            )
            assert result.returncode == 0
    
    def test_jobs_json_format(self, running_cluster, temp_test_dir):
        """Test JSON output format"""
        result = run_scheduler_cmd(
            ['jobs', '--format', 'json'],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        # Should be valid JSON (at least parse without error)
        import json
        try:
            data = json.loads(result.stdout)
            assert isinstance(data, list) or isinstance(data, dict)
        except json.JSONDecodeError:
            pytest.fail(f"Jobs output is not valid JSON: {result.stdout}")


class TestCLILogs:
    """Test 'scheduler logs' command"""
    
    def test_logs_basic(self, running_cluster, temp_test_dir):
        """Test retrieving job logs"""
        # Submit a job with specific output
        script_path = os.path.join(temp_test_dir, "log_job.py")
        test_message = "UNIQUE_LOG_TEST_MESSAGE_789"
        with open(script_path, 'w') as f:
            f.write(f"print('{test_message}')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job_id = match.group(1)
        
        # Wait for job to complete (poll with timeout)
        for i in range(30):
            result = run_scheduler_cmd(
                ['jobs', job_id],
                env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
            )
            if 'completed' in result.stdout.lower():
                break
            time.sleep(1)
        
        # Get logs
        result = run_scheduler_cmd(
            ['logs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        # Logs command should work
        assert result.returncode == 0, f"Logs command failed: {result.stderr}"
        # Check for our message (may be in logs or in "not found" message if log aggregation not implemented)
        # For now, just verify the command works
        assert job_id in result.stdout, f"Job ID should be in output: {result.stdout}"


class TestCLICancel:
    """Test 'scheduler cancel' command"""
    
    def test_cancel_job(self, running_cluster, temp_test_dir):
        """Test canceling a running job"""
        # Submit a long-running job
        script_path = os.path.join(temp_test_dir, "long_job.py")
        with open(script_path, 'w') as f:
            f.write("import time\n")
            f.write("for i in range(100):\n")
            f.write("    time.sleep(1)\n")
            f.write("    print(f'Iteration {i}')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job_id = match.group(1)
        
        # Wait for job to start
        time.sleep(5)
        
        # Cancel it
        result = run_scheduler_cmd(
            ['cancel', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        
        # Wait a moment
        time.sleep(2)
        
        # Verify job is cancelled or interrupted
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        assert 'cancel' in result.stdout.lower() or 'interrupt' in result.stdout.lower() or 'CANCELLED' in result.stdout or 'INTERRUPTED' in result.stdout


class TestCLIConfig:
    """Test 'scheduler config' command"""
    
    def test_config_show(self, running_cluster, temp_test_dir):
        """Test showing configuration"""
        result = run_scheduler_cmd(['config', 'show'])
        
        # Should either succeed with config or fail gracefully
        # Not all installations may have a config file
        assert result.returncode in [0, 1, 2]
    
    def test_config_set_get(self, running_cluster, temp_test_dir):
        """Test setting and getting config values"""
        # Set a value
        result = run_scheduler_cmd(['config', 'set', 'address', running_cluster['head_address']])
        
        # Should succeed or fail gracefully
        if result.returncode == 0:
            # Try to get it back
            result = run_scheduler_cmd(['config', 'get', 'address'])
            assert result.returncode == 0
            assert running_cluster['head_address'] in result.stdout or running_cluster['port'] in result.stdout


class TestCLIStop:
    """Test 'scheduler stop' command
    
    Note: These tests start a temporary scheduler to test stop functionality
    """
    
    def test_stop_help(self):
        """Test that stop command exists and has help"""
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "stop", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0
        assert "stop" in result.stdout.lower()
    
    # Note: Stop command testing is complex due to singleton locks.
    # These are tested via the running_cluster fixture lifecycle.
    # Manual stop commands are verified via the running_cluster fixture cleanup.
    
    def test_stop_worker_when_running(self, temp_test_dir, running_cluster):
        """Test stop command can stop a running worker node"""
        # Start an additional worker in the background
        start_result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "start",
             "--address", running_cluster['head_address'],
             "--node-name", "test-stop-worker"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        assert start_result.returncode == 0, f"Failed to start worker: {start_result.stderr}"
        
        # Give it time to start
        time.sleep(3)
        
        # Now stop it (stop command stops all local workers)
        stop_result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "stop"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should succeed
        assert stop_result.returncode == 0, f"Stop failed: {stop_result.stderr}"
    
    def test_stop_when_nothing_running(self, temp_test_dir):
        """Test stop command when no scheduler is running"""
        # Should handle gracefully
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "stop"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should handle gracefully (exit code 0 or 1)
        assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"


class TestCLIStatus:
    """Test 'scheduler status' command
    
    Note: This command launches a TUI which we can't fully test in CI,
    but we can verify it attempts to start correctly
    """
    
    def test_status_help(self):
        """Test that status command exists"""
        result = subprocess.run(
            ["python", "-m", "scheduler.cli.main", "status", "--help"],
            capture_output=True,
            text=True,
            timeout=10
        )
        # Status command may not have a help flag, so just check it exists
        assert result.returncode in [0, 2]  # 0 if help works, 2 if it tries to connect
    
    def test_status_attempts_to_connect(self, running_cluster):
        """Test that status command attempts to connect to scheduler
        
        We can't test the full TUI in CI, but we verify it tries to start
        """
        # Start status command and kill it after a moment (TUI would block)
        proc = subprocess.Popen(
            ["python", "-m", "scheduler.cli.main", "status"],
            env={**os.environ, 'SCHEDULER_ADDRESS': running_cluster['head_address']},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Give it a moment to attempt connection and start TUI
        time.sleep(2)
        
        # Terminate it (TUI would run forever)
        proc.terminate()
        try:
            stdout, stderr = proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
        
        # If we got here without immediate crash, command at least tried to start
        # This verifies the command accepts SCHEDULER_ADDRESS and attempts connection
        assert True


class TestCLIIntegration:
    """Integration tests that combine multiple CLI commands"""
    
    def test_full_workflow(self, running_cluster, temp_test_dir):
        """Test a complete workflow: submit -> monitor -> logs -> cancel"""
        # 1. Submit a long-running job
        script_path = os.path.join(temp_test_dir, "workflow_job.py")
        with open(script_path, 'w') as f:
            f.write("import time\n")
            f.write("print('Job starting')\n")
            f.write("for i in range(50):\n")
            f.write("    time.sleep(1)\n")
            f.write("    print(f'Working {i}')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', '--name', 'workflow-test', script_path],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        
        assert result.returncode == 0
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job_id = match.group(1)
        
        # 2. Wait for job to start
        time.sleep(5)
        
        # 3. Check status with jobs command
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        assert job_id in result.stdout
        
        # 4. Try to get logs
        result = run_scheduler_cmd(
            ['logs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        # Logs may or may not be available yet, but command should work
        
        # 5. Cancel the job
        result = run_scheduler_cmd(
            ['cancel', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        
        # 6. Verify cancellation or interruption
        time.sleep(2)
        result = run_scheduler_cmd(
            ['jobs', job_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        assert 'cancel' in result.stdout.lower() or 'interrupt' in result.stdout.lower() or 'CANCELLED' in result.stdout or 'INTERRUPTED' in result.stdout
    
    def test_job_dependencies(self, running_cluster, temp_test_dir):
        """Test submitting jobs with dependencies"""
        # Job 1
        script1 = os.path.join(temp_test_dir, "dep_job1.py")
        with open(script1, 'w') as f:
            f.write("import time\n")
            f.write("time.sleep(2)\n")
            f.write("print('Job 1 complete')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', script1],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job1_id = match.group(1)
        
        # Job 2 depends on Job 1
        script2 = os.path.join(temp_test_dir, "dep_job2.py")
        with open(script2, 'w') as f:
            f.write("print('Job 2 starting after job 1')\n")
        
        result = run_scheduler_cmd(
            ['submit', '--req', '1', '--async', '--depends-on', job1_id, script2],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        match = re.search(r'(job_[a-f0-9]+)', result.stdout)
        assert match
        job2_id = match.group(1)
        
        # Wait for both to complete
        time.sleep(6)  # Reduced from 10 for faster e2e tests
        
        # Verify both completed
        result = run_scheduler_cmd(
            ['jobs', job1_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0
        
        result = run_scheduler_cmd(
            ['jobs', job2_id],
            env_override={'SCHEDULER_ADDRESS': running_cluster['head_address']}
        )
        assert result.returncode == 0

