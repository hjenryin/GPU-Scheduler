from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, JobNotFoundException
import click


def logs_command(
    job_id: str,
    follow: bool = False,
    lines: int = 100,
    timestamps: bool = False,
    stderr: bool = False,
    both: bool = False
) -> int:
    """
    View logs for a specific job.

    Args:
        job_id: Job ID to view logs for
        follow: If True, follow logs in real-time
        lines: Number of lines to show from end
        timestamps: If True, show timestamps
        stderr: If True, show stderr instead of stdout
        both: If True, show both stdout and stderr

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        if both:
            click.echo("=== STDOUT ===")
            click.echo(client.get_job_logs(job_id, lines=lines, stderr=False))
            click.echo("\n=== STDERR ===")
            click.echo(client.get_job_logs(job_id, lines=lines, stderr=True))
        elif follow:
            click.echo(f"Following logs for job {job_id} (Ctrl+C to stop)...")
            try:
                for line in client.stream_job_logs(job_id, stderr=stderr):
                    click.echo(line)
            except KeyboardInterrupt:
                click.echo("\nStopped following logs")
        else:
            logs = client.get_job_logs(job_id, lines=lines, stderr=stderr)
            click.echo(logs)

        return 0

    except JobNotFoundException as e:
        click.echo(f"Job not found: {e}")
        return 4
    except ConnectionException as e:
        click.echo(f"Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
