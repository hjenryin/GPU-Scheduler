import click
from datetime import datetime

from scheduler.api import SchedulerClient
from scheduler.core import (
    load_config, ConnectionException, JobNotFoundException,
    ValidationException, parse_time_duration
)


def purge_command(
    target: str,
    failed: bool = False,
    completed: bool = False,
    cancelled: bool = False
) -> int:
    """
    Purge jobs based on time duration or specific job ID.

    Args:
        target: Either a job_id or time duration string (e.g., "7d", "3w", "24h")
        failed: Only purge failed jobs
        completed: Only purge completed jobs
        cancelled: Only purge cancelled jobs

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found (when purging by job_id)
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        # Determine status filter
        status_filter = None
        if failed or completed or cancelled:
            # If any flag is set, only purge those types
            status_filter = []
            if failed:
                status_filter.append('failed')
            if completed:
                status_filter.append('completed')
            if cancelled:
                status_filter.append('cancelled')
        else:
            # If no flags set, purge all terminal states
            status_filter = ['failed', 'completed', 'cancelled']

        # Try to parse as time duration first
        try:
            duration = parse_time_duration(target)
            # Calculate cutoff time
            cutoff_time = datetime.now() - duration

            click.echo(
                f"Purging jobs older than {target} "
                f"(before {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')})..."
            )
            click.echo(f"Status filter: {', '.join(status_filter)}")

            result = client.purge_jobs(
                before_time=cutoff_time,
                status_filter=status_filter
            )

            purged_count = result.get('purged_count', 0)
            if purged_count > 0:
                click.echo(f"✓ Successfully marked {purged_count} job(s) for purging")
                click.echo("  Jobs will be cleaned up on workers during next heartbeat")
            else:
                click.echo("No jobs found matching the criteria")

            return 0

        except ValidationException:
            # Not a time duration, try as job_id
            job_id = target

            click.echo(f"Purging job: {job_id}...")

            try:
                result = client.purge_job(job_id)
                click.echo(f"✓ Successfully marked job {job_id} for purging")
                click.echo("  Job will be cleaned up on worker during next heartbeat")
                return 0
            except JobNotFoundException:
                click.echo(f"❌ Job not found: {job_id}")
                return 1

    except ConnectionException as e:
        click.echo(f"❌ Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        return 1
