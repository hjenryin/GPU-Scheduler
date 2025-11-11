"""Retry job CLI command"""

import logging
from typing import Optional

import click

from scheduler.api.client import SchedulerClient
from scheduler.core import JobNotFoundException, ValidationException, ConnectionException

logger = logging.getLogger(__name__)


@click.command()
@click.argument('job_id')
@click.option('--inplace', is_flag=True, help='Revert job to pending in-place (same job_id)')
@click.option('--then', 'then_mode', is_flag=True, help='Retry from original commit (new job_id)')
@click.option('--now', is_flag=True, help='Retry with fresh snapshot (new job_id)')
def retry(job_id: str, inplace: bool, then_mode: bool, now: bool):
    """
    Retry a failed, cancelled, or completed job.

    Exactly one of --inplace, --then, or --now must be specified:

    \b
    --inplace: Revert the job to PENDING state with the same job_id.
               The job will re-execute in the original branch from the
               "before" commit. Any "after" commit will be overwritten.

    \b
    --then: Create a new job with a new job_id, but using the same
            snapshot (before commit) as the original job. This creates
            a new branch pointing to the original commit.

    \b
    --now: Create a new job with a new job_id and a fresh snapshot
           from the current working directory state. This is equivalent
           to resubmitting the job.

    Examples:

    \b
        scheduler retry abc123 --inplace
        scheduler retry abc123 --then
        scheduler retry abc123 --now
    """
    # Validate exactly one flag is set
    flags_set = sum([inplace, then_mode, now])
    if flags_set == 0:
        click.echo("Error: Must specify exactly one of --inplace, --then, or --now", err=True)
        raise click.Exit(1)
    elif flags_set > 1:
        click.echo("Error: Can only specify one of --inplace, --then, or --now", err=True)
        raise click.Exit(1)

    try:
        client = SchedulerClient()

        if inplace:
            # HEAD-side operation
            click.echo(f"Retrying job {job_id} in-place...")
            response = client.session.post(
                f"{client.base_url}/jobs/{job_id}/retry-inplace",
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            click.echo(f"✓ Job {job_id} reset to PENDING (in-place)")
            click.echo(f"  The job will re-execute in the original branch")

        elif then_mode:
            # CLIENT-side operation
            click.echo(f"Retrying job {job_id} from original commit...")
            new_job = client.retry_job_then(job_id)
            click.echo(f"✓ Created new job {new_job.job_id} from original commit")
            click.echo(f"  Original job: {job_id}")
            click.echo(f"  New job: {new_job.job_id}")
            click.echo(f"  Status: {new_job.status.value}")

        elif now:
            # CLIENT-side operation
            click.echo(f"Retrying job {job_id} with fresh snapshot...")
            new_job = client.retry_job_now(job_id)
            click.echo(f"✓ Created new job {new_job.job_id} with fresh snapshot")
            click.echo(f"  Original job: {job_id}")
            click.echo(f"  New job: {new_job.job_id}")
            click.echo(f"  Status: {new_job.status.value}")

    except JobNotFoundException as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
    except ValidationException as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
    except ConnectionException as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        logger.exception("Unexpected error during retry")
        raise click.Exit(1)
