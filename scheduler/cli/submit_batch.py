import os
import time
from typing import List, Optional
import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ValidationException, ConnectionException
from scheduler.worker.git_snapshot import GitSnapshotManager


def submit_batch_command(
    script_list: str,
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    working_dir: Optional[str] = None,
    async_submit: bool = False,
    log_to_driver: bool = False,
    sequential: bool = False
) -> int:
    """
    Submit multiple jobs from a file containing script paths.

    Args:
        script_list: Path to file containing script paths (one per line)
        req: Resource requirement string (applied to all jobs)
        depends_on: List of job IDs to depend on (applied to all jobs)
        name: Base job name (applied to all jobs)
        priority: Job priority (applied to all jobs)
        env: List of "KEY=VALUE" environment variables (applied to all jobs)
        working_dir: Working directory for jobs (applied to all jobs)
        async_submit: If True, return immediately after submission
        log_to_driver: If True, stream logs to stdout (only for last job)
        sequential: If True, each job depends on the previous job

    Returns:
        Exit code (0 for success)

    Raises:
        FileNotFoundError: If script_list file doesn't exist
    """
    # Validate script list file
    if not os.path.exists(script_list):
        click.echo(f"Error: Script list file not found: {script_list}")
        return 4

    # Read scripts from file
    try:
        with open(script_list, 'r') as f:
            lines = [line.strip() for line in f if line.strip()]
    except IOError as e:
        click.echo(f"Error: Cannot read script list file: {e}")
        return 1

    if not lines:
        click.echo("Error: Script list file is empty")
        return 1

    # Parse each line into script and args
    scripts_with_args = []
    for line in lines:
        parts = line.split()
        if parts:
            script = parts[0]
            script_args = parts[1:] if len(parts) > 1 else []
            scripts_with_args.append((script, script_args))

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

    # If working directory is not specified, use the current directory
    # This ensures jobs run in the directory where they were submitted from
    if working_dir is None:
        working_dir = os.getcwd()

    # Check if working directory is in a git repository
    # If not, ask user to confirm the workspace
    try:
        config = load_config()
        git_manager = GitSnapshotManager(config)
        
        if not git_manager.is_git_repository(working_dir):
            # Not in a git repo - inform user and ask for confirmation
            click.echo(f"\n⚠️  Working directory is not in a git repository: {working_dir}")
            click.echo("\nThe scheduler will create a shadow repository (.scheduler-git) to track job snapshots.")
            click.echo("This ensures jobs run with consistent file versions even if you modify files while they're queued.")
            
            # Ask user to confirm or provide alternate workspace
            if not click.confirm(f"\nUse '{working_dir}' as workspace?", default=True):
                workspace = click.prompt("Enter workspace path", type=str, default=working_dir)
                working_dir = os.path.abspath(workspace)
                
                if not os.path.isdir(working_dir):
                    click.echo(f"Error: Directory does not exist: {working_dir}")
                    return 4
    except Exception as e:
        # Don't fail submission if git check fails, just log and continue
        click.echo(f"Warning: Could not check git repository status: {e}")

    click.echo(f"Submitting {len(scripts_with_args)} jobs from {script_list}")
    if sequential:
        click.echo("Sequential mode: Each job will depend on the previous job")
    
    # Submit each script
    failed = 0
    succeeded = 0
    previous_job_id = None
    submitted_jobs = []
    
    try:
        # Connect to scheduler
        config = load_config()
        client = SchedulerClient(config=config)
        
        for i, (script, script_args) in enumerate(scripts_with_args):
            # Validate script exists
            if not os.path.exists(script):
                click.echo(f"\n[{i+1}/{len(scripts_with_args)}] Error: Script not found: {script}")
                failed += 1
                if sequential:
                    click.echo("Sequential mode: Stopping batch submission due to error")
                    break
                continue
            
            # Display script with args if any
            script_display = f"{os.path.basename(script)}"
            if script_args:
                script_display += f" {' '.join(script_args)}"
            click.echo(f"\n[{i+1}/{len(scripts_with_args)}] Submitting job: {script_display}")
            
            # Get absolute script path
            abs_script = os.path.abspath(script)
            
            # Determine dependencies
            job_depends_on = depends_on.copy() if depends_on else []
            if sequential and previous_job_id:
                job_depends_on.append(previous_job_id)
            
            try:
                # Submit job
                job = client.submit_job(
                    script=abs_script,
                    requirements=req,
                    name=name,
                    script_args=script_args if script_args else None,
                    working_dir=working_dir,
                    env_vars=env_vars,
                    dependencies=job_depends_on if job_depends_on else None,
                    priority=priority,
                )
                
                click.echo(f"\nJob submitted successfully!")
                click.echo(f"Job ID: {job.job_id}")
                click.echo(f"Status: {job.status.value}")
                click.echo(f"Requirements: {req}")
                if job_depends_on:
                    click.echo(f"Dependencies: {', '.join(job_depends_on)}")
                
                succeeded += 1
                submitted_jobs.append(job)
                previous_job_id = job.job_id
                
            except ValidationException as e:
                click.echo(f"Validation error: {e}")
                failed += 1
                if sequential:
                    click.echo("Sequential mode: Stopping batch submission due to error")
                    break
            except ConnectionException as e:
                click.echo(f"❌ Connection error: {e}")
                failed += 1
                if sequential:
                    click.echo("Sequential mode: Stopping batch submission due to error")
                    break
            except Exception as e:
                click.echo(f"Error: {e}")
                failed += 1
                if sequential:
                    click.echo("Sequential mode: Stopping batch submission due to error")
                    break
        
        # Summary
        click.echo(f"\n{'='*50}")
        click.echo(f"Batch submission complete:")
        click.echo(f"  Succeeded: {succeeded}/{len(scripts_with_args)}")
        click.echo(f"  Failed: {failed}/{len(scripts_with_args)}")
        click.echo(f"{'='*50}")
        
        # Handle log streaming for last job if requested
        if log_to_driver and submitted_jobs:
            last_job = submitted_jobs[-1]
            click.echo(f"\nStreaming logs for last job ({last_job.job_id}) (Ctrl+C to stop)...")
            try:
                for line in client.stream_job_logs(last_job.job_id):
                    click.echo(line)
            except KeyboardInterrupt:
                click.echo("\nStopped streaming logs")
        
        # Wait for last job completion if not async
        elif not async_submit and submitted_jobs:
            last_job = submitted_jobs[-1]
            click.echo(f"\nWaiting for last job ({last_job.job_id}) to complete...")
            while True:
                job = client.get_job(last_job.job_id)
                if job.status.value in ['completed', 'failed', 'cancelled']:
                    break
                time.sleep(2)
            
            click.echo(f"\nJob {job.status.value}")
            if job.exit_code is not None:
                click.echo(f"Exit code: {job.exit_code}")
            if job.error_message:
                click.echo(f"Error: {job.error_message}")
            
            return 0 if job.status.value == 'completed' else 1
        
        return 0 if failed == 0 else 1
        
    except ValidationException as e:
        click.echo(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        click.echo(f"❌ Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
