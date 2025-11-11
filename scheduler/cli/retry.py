import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, JobNotFoundException


def retry_command(job_id: str, mode: str = "inplace") -> int:
    """
    Retry a failed, cancelled, or completed job.

    Args:
        job_id: Job ID to retry
        mode: Retry mode - "inplace", "then", or "now"
            - inplace: Retry job in place by reverting to PENDING status (reuse same job ID and snapshot, default)
            - then: Create new job with same config and normal priority
            - now: Create new job with same config and high priority

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        # Retry the job with specified mode
        result = client.retry_job(job_id, mode=mode)

        if mode == "inplace":
            click.echo(f"Job {job_id} has been reset and will be retried")
            click.echo(f"Status: {result['status']}")
        else:
            new_job_id = result['new_job_id']
            click.echo(f"Created new job {new_job_id} (retry of {job_id})")
            click.echo(f"Status: {result['status']}")
            if mode == "now":
                click.echo(f"Priority: High (will run before normal jobs)")

        return 0

    except JobNotFoundException:
        click.echo(f"Job not found: {job_id}")
        return 1
    except ConnectionException as e:
        click.echo(f"Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
