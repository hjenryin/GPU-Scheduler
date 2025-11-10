import os
import time
import shutil
import shlex
from typing import List, Optional
import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ValidationException, ConnectionException


def submit_batch_command(
    script_list: str,
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    working_dir: Optional[str] = None,
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
            lines = [line.strip() for line in f if line.strip() and not line.strip().startswith('#')]
    except IOError as e:
        click.echo(f"Error: Cannot read script list file: {e}")
        return 1

    if not lines:
        click.echo("Error: Script list file is empty")
        return 1

    # Parse each line into script and args
    scripts_with_args = []
    for line in lines:
        # Use shlex.split so quoted arguments are handled correctly
        parts = shlex.split(line)
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

    click.echo(f"Submitting {len(scripts_with_args)} jobs from {script_list}")
    if sequential:
        click.echo("Sequential mode: Each job will depend on the previous job")
    
    # Use current directory if not specified (must be set on client side, not server side)
    if working_dir is None:
        working_dir = os.getcwd()
    
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
            # Align behavior with `submit` CLI: don't validate script existence here.
            # Treat the first token as the script/command and remaining tokens as args.
            # Let the server/worker handle command resolution and errors.
            command_elements = [script] + (script_args if script_args else [])
            command_str = ' '.join(command_elements)
            click.echo(f"\n[{i+1}/{len(scripts_with_args)}] Submitting job: {command_str}")

            # If the script looks like a filesystem path (contains a directory component),
            # convert it to an absolute path so the server receives the correct path. If it's
            # a bare command name, leave it as-is for resolution on the worker.
            abs_script = os.path.abspath(script) if os.path.dirname(script) else script

            # Determine dependencies
            job_depends_on = depends_on.copy() if depends_on else []
            if sequential and previous_job_id:
                job_depends_on.append(previous_job_id)

            # Store original dependencies for comparison
            original_job_depends_on = job_depends_on.copy()

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

                # Show resolved dependencies
                if job.dependencies:
                    dep_display = []
                    for i, resolved_dep in enumerate(job.dependencies):
                        if i < len(original_job_depends_on) and original_job_depends_on[i] != resolved_dep:
                            dep_display.append(f"{resolved_dep} (resolved)")
                        else:
                            dep_display.append(resolved_dep)
                    click.echo(f"Dependencies: {', '.join(dep_display)}")

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
