import os
import time
from typing import List, Optional
import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ValidationException, ConnectionException


def submit_command(
    command: List[str],
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    working_dir: Optional[str] = None,
    async_submit: bool = False,
    log_to_driver: bool = False
) -> int:
    """
    Submit a new job to the scheduler.

    Args:
        command: Command to execute as a list (e.g., ['python', 'train.py', '--epochs', '10'])
        req: Resource requirement string
        depends_on: List of job IDs to depend on
        name: Human-readable job name
        priority: Job priority
        env: List of "KEY=VALUE" environment variables
        working_dir: Working directory for job
        async_submit: If True, return immediately after submission
        log_to_driver: If True, stream logs to stdout

    Returns:
        Exit code (0 for success)

    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node
    """
    # Validate command
    if not command or len(command) == 0:
        click.echo("Error: Command cannot be empty")
        return 4

    # Parse environment variables
    env_vars = {}
    if env:
        for env_var in env:
            if '=' not in env_var:
                click.echo(f"Error: Invalid environment variable format: {env_var}")
                click.echo("Expected format: KEY=VALUE")
                return 2
            key, value = env_var.split('=', 1)
            env_vars[key] = value

    # Store command as script (first element) and script_args (remaining elements)
    # This maintains backward compatibility with the Job model
    script = command[0]
    script_args = command[1:] if len(command) > 1 else None

    # Use current directory if not specified (must be set on client side, not server side)
    if working_dir is None:
        working_dir = os.getcwd()

    try:
        # Connect to scheduler
        config = load_config()
        client = SchedulerClient(config=config)

        # Submit job - use the full command as the display name
        command_str = ' '.join(command)
        click.echo(f"Submitting job: {command_str}")
        job = client.submit_job(
            script=script,
            requirements=req,
            name=name,
            script_args=script_args,
            working_dir=working_dir,
            env_vars=env_vars,
            dependencies=depends_on,
            priority=priority,
        )

        click.echo(f"\nJob submitted successfully!")
        click.echo(f"Job ID: {job.job_id}")
        click.echo(f"Status: {job.status.value}")
        click.echo(f"Requirements: {req}")
        click.echo(f"\nView status: scheduler status (then press 'J' and search for job)")

        if log_to_driver:
            click.echo(f"\nStreaming logs (Ctrl+C to stop)...")
            try:
                for line in client.stream_job_logs(job.job_id):
                    click.echo(line)
            except KeyboardInterrupt:
                click.echo("\nStopped streaming logs")

        elif not async_submit:
            click.echo(f"\nWaiting for job to complete...")
            while True:
                job = client.get_job(job.job_id)
                if job.status.value in ['completed', 'failed', 'cancelled']:
                    break
                time.sleep(2)

            click.echo(f"\nJob {job.status.value}")
            if job.exit_code is not None:
                click.echo(f"Exit code: {job.exit_code}")
            if job.error_message:
                click.echo(f"Error: {job.error_message}")

            return 0 if job.status.value == 'completed' else 1

        return 0

    except ValidationException as e:
        click.echo(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        click.echo(f"❌ Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
