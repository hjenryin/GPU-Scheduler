import json
from typing import List, Optional
from datetime import datetime
import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException


def jobs_command(
    job_ids: List[str] = None,
    format: str = "table",
    filter: str = "all",
    limit: int = 50
) -> int:
    """
    List jobs in non-interactive mode.

    Args:
        job_ids: Specific job IDs to query (None for all)
        format: Output format ("table", "json", "yaml")
        filter: Filter by status ("all", "pending", "running", "completed", "failed")
        limit: Maximum number of jobs to show

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If specified job not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        if job_ids:
            for job_id in job_ids:
                job = client.get_job(job_id)
                if format == "json":
                    click.echo(json.dumps(job.to_dict(), indent=2))
                else:
                    _print_job_details(job)
        else:
            jobs = client.list_jobs(status_filter=filter if filter != "all" else None, limit=limit)
            if format == "json":
                click.echo(json.dumps([j.to_dict() for j in jobs], indent=2))
            else:
                _print_job_table(jobs)

        return 0
    except ConnectionException as e:
        click.echo(f"Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1


def _print_job_table(jobs):
    if not jobs:
        click.echo("No jobs found")
        return
    click.echo(f"{'JOB_ID':<18} {'NAME':<20} {'STATUS':<12} {'NODE':<10} {'GPUS':<6} {'RUNTIME':<12}")
    click.echo("-" * 90)
    for job in jobs:
        runtime = "-"
        if job.started_at:
            duration = ((job.completed_at or datetime.now()) - job.started_at).total_seconds()
            h, r = divmod(int(duration), 3600)
            m, s = divmod(r, 60)
            runtime = f"{h:02d}:{m:02d}:{s:02d}"
        gpus = len(job.assigned_gpus) if job.assigned_gpus else 0
        click.echo(f"{job.job_id:<18} {job.name:<20} {job.status.value:<12} {job.assigned_node or '-':<10} {gpus:<6} {runtime:<12}")


def _print_job_details(job):
    click.echo(f"\nJob: {job.job_id}")
    click.echo(f"Name: {job.name}")
    click.echo(f"Status: {job.status.value}")
    if job.assigned_node:
        click.echo(f"Node: {job.assigned_node}, GPUs: {job.assigned_gpus}")
    if job.exit_code is not None:
        click.echo(f"Exit code: {job.exit_code}")
    if job.error_message:
        click.echo(f"Error: {job.error_message}")
    click.echo()
