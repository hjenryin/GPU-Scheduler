import os
from typing import List, Optional
import click

from scheduler.cli.submit import submit_command


def submit_batch_command(
    script_list: str,
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
            scripts = [line.strip() for line in f if line.strip()]
    except IOError as e:
        click.echo(f"Error: Cannot read script list file: {e}")
        return 1

    if not scripts:
        click.echo("Error: Script list file is empty")
        return 1

    click.echo(f"Submitting {len(scripts)} jobs from {script_list}")
    
    # Submit each script
    failed = 0
    succeeded = 0
    
    for i, script in enumerate(scripts):
        click.echo(f"\n[{i+1}/{len(scripts)}] Submitting: {script}")
        
        # For batch submission, we want async mode for all but optionally wait for the last one
        # If log_to_driver is set, only apply it to the last job
        is_last = (i == len(scripts) - 1)
        current_async = async_submit if is_last else True
        current_log_to_driver = log_to_driver if is_last else False
        
        result = submit_command(
            script=script,
            script_args=None,
            req=req,
            depends_on=depends_on,
            name=name,
            priority=priority,
            env=env,
            working_dir=working_dir,
            async_submit=current_async,
            log_to_driver=current_log_to_driver
        )
        
        if result == 0:
            succeeded += 1
        else:
            failed += 1
            click.echo(f"Warning: Failed to submit {script} (exit code: {result})")
    
    # Summary
    click.echo(f"\n{'='*50}")
    click.echo(f"Batch submission complete:")
    click.echo(f"  Succeeded: {succeeded}/{len(scripts)}")
    click.echo(f"  Failed: {failed}/{len(scripts)}")
    click.echo(f"{'='*50}")
    
    return 0 if failed == 0 else 1
