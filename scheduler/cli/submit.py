import os
import time
from typing import List, Optional

from scheduler.api.client import SchedulerClient
from scheduler.core.config import load_config
from scheduler.core.exceptions import ValidationException, ConnectionException


def submit_command(
    script: str,
    script_args: List[str] = None,
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    timeout: Optional[int] = None,
    working_dir: Optional[str] = None,
    async_submit: bool = False,
    log_to_driver: bool = False
) -> int:
    """
    Submit a new job to the scheduler.

    Args:
        script: Path to script to execute
        script_args: Arguments to pass to script
        req: Resource requirement string
        depends_on: List of job IDs to depend on
        name: Human-readable job name
        priority: Job priority
        env: List of "KEY=VALUE" environment variables
        timeout: Job timeout in seconds
        working_dir: Working directory for job
        async_submit: If True, return immediately after submission
        log_to_driver: If True, stream logs to stdout

    Returns:
        Exit code (0 for success)

    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node
        FileNotFoundError: If script doesn't exist
    """
    # Validate script path
    if not os.path.exists(script):
        print(f"Error: Script not found: {script}")
        return 4

    # Parse environment variables
    env_vars = {}
    if env:
        for env_var in env:
            if '=' not in env_var:
                print(f"Error: Invalid environment variable format: {env_var}")
                print("Expected format: KEY=VALUE")
                return 2
            key, value = env_var.split('=', 1)
            env_vars[key] = value

    # Get absolute script path
    script = os.path.abspath(script)

    try:
        # Connect to scheduler
        config = load_config()
        client = SchedulerClient(config=config)

        # Submit job
        print(f"Submitting job: {os.path.basename(script)}")
        job = client.submit_job(
            script=script,
            requirements=req,
            name=name,
            script_args=script_args,
            working_dir=working_dir,
            env_vars=env_vars,
            dependencies=depends_on,
            priority=priority,
            timeout=timeout
        )

        print(f"\nJob submitted successfully!")
        print(f"Job ID: {job.job_id}")
        print(f"Status: {job.status.value}")
        print(f"Requirements: {req}")
        print(f"\nView status: scheduler status (then press 'J' and search for job)")

        if log_to_driver:
            print(f"\nStreaming logs (Ctrl+C to stop)...")
            try:
                for line in client.stream_job_logs(job.job_id):
                    print(line)
            except KeyboardInterrupt:
                print("\nStopped streaming logs")

        elif not async_submit:
            print(f"\nWaiting for job to complete...")
            while True:
                job = client.get_job(job.job_id)
                if job.status.value in ['completed', 'failed', 'cancelled']:
                    break
                time.sleep(2)

            print(f"\nJob {job.status.value}")
            if job.exit_code is not None:
                print(f"Exit code: {job.exit_code}")
            if job.error_message:
                print(f"Error: {job.error_message}")

            return 0 if job.status.value == 'completed' else 1

        return 0

    except ValidationException as e:
        print(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        print(f"Connection error: {e}")
        print("\nCannot connect to head node. Is it running?")
        print("Start head node with: scheduler start --head")
        return 3
    except Exception as e:
        print(f"Error: {e}")
        return 1
