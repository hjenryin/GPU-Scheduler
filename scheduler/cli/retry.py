import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, JobNotFoundException, JobStatus


def retry_command(
    job_id: str,
    inplace: bool = False,
    then: bool = False,
    now: bool = False
) -> int:
    """
    Retry a failed, cancelled, or completed job.

    Args:
        job_id: Job ID to retry
        inplace: Use --inplace mode (reset job to PENDING, reuse same job ID)
        then: Use --then mode (create new job with original snapshot)
        now: Use --now mode (create new job with fresh snapshot from current state)

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        # Check that at most one flag is specified
        flag_count = sum([inplace, then, now])
        if flag_count > 1:
            click.echo("Error: Only one of --inplace, --then, or --now can be specified")
            return 2

        # Determine mode
        if inplace:
            mode = "inplace"
        elif then:
            mode = "then"
        elif now:
            mode = "now"
        else:
            # No flag specified - determine default based on job status
            try:
                job = client.get_job(job_id)

                # Default: FAILED/CANCELLED → inplace, COMPLETED → then
                if job.status in [JobStatus.FAILED, JobStatus.CANCELLED]:
                    mode = "inplace"
                    click.echo(f"Job is {job.status.value}, using --inplace mode (default)")
                elif job.status == JobStatus.COMPLETED:
                    mode = "then"
                    click.echo(f"Job is completed, using --then mode (default)")
                else:
                    click.echo(f"Error: Job is in {job.status.value} state. "
                             f"Only FAILED, CANCELLED, or COMPLETED jobs can be retried.")
                    return 2

            except JobNotFoundException:
                click.echo(f"Job not found: {job_id}")
                return 1

        # Retry the job with specified mode
        result = client.retry_job(job_id, mode=mode)

        if mode == "inplace":
            click.echo(f"Job {job_id} has been reset to PENDING and will be retried")
            click.echo(f"Status: {result['status']}")
        else:
            new_job_id = result['new_job_id']
            click.echo(f"Created new job {new_job_id} (retry of {job_id})")
            click.echo(f"Status: {result['status']}")
            if mode == "now":
                click.echo(f"Priority: High (will run before normal jobs)")
            else:
                click.echo(f"Priority: Normal")

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
