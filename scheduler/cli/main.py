import click
import sys

from scheduler.cli.start import start_command
from scheduler.cli.stop import stop_command
from scheduler.cli.submit import submit_command
from scheduler.cli.submit_batch import submit_batch_command
from scheduler.cli.jobs import jobs_command
from scheduler.cli.logs import logs_command
from scheduler.cli.cancel import cancel_command
from scheduler.cli.retry import retry
from scheduler.cli.config import config_command
from scheduler.cli.status import status_command
from scheduler.cli.purge import purge_command
from scheduler.cli.freeze import freeze_command
from scheduler.cli.unfreeze import unfreeze_command


@click.group()
@click.version_option(version='0.1.0')
def cli():
    """GPU Scheduler - Distributed job scheduling across GPU machines"""
    pass


@cli.command()
@click.option('--head', is_flag=True, help='Start as head node')
@click.option('--address', help='Head node address (for workers)')
@click.option('--port', type=int, default=8265, help='Port number')
@click.option('--node-name', help='Node name')
@click.option('--num-gpus', type=int, help='Number of GPUs')
@click.option('--temp-dir', help='Temporary directory')
@click.option('--log-dir', help='Log directory')
@click.option('--block', is_flag=True, default=False, help='Block until stopped')
@click.option('--log-level', default='INFO', help='Log level')
@click.option('--heartbeat-timeout', type=int, help='Heartbeat timeout (head only)')
@click.option('--scheduling-interval', type=int, help='Scheduling interval (head only)')
@click.option('--graceful-shutdown-timeout', type=int, help='Graceful shutdown timeout in seconds (head only)')
@click.option('--gpu-poll-interval', type=int, help='GPU poll interval (worker only)')
@click.option('--gpu-util-threshold', type=int, help='GPU utilization threshold (worker only)')
@click.option('--gpu-mem-threshold', type=int, help='GPU memory threshold (worker only)')
@click.option('--gpu-stable-time', type=int, help='GPU stable time (worker only)')
@click.option('--job-startup-grace', type=int, help='Job startup grace period (worker only)')
def start(head, address, port, node_name, num_gpus, temp_dir, log_dir, block, log_level,
          heartbeat_timeout, scheduling_interval, graceful_shutdown_timeout,
          gpu_poll_interval, gpu_util_threshold, gpu_mem_threshold, gpu_stable_time, job_startup_grace):
    """Start scheduler node"""
    try:
            code = start_command(
            head=head,
            address=address,
            port=port,
            node_name=node_name,
            num_gpus=num_gpus,
            temp_dir=temp_dir,
            log_dir=log_dir,
            block=block,
            log_level=log_level,
            heartbeat_timeout=heartbeat_timeout,
            scheduling_interval=scheduling_interval,
            graceful_shutdown_timeout=graceful_shutdown_timeout,
            gpu_poll_interval=gpu_poll_interval,
            gpu_util_threshold=gpu_util_threshold,
            gpu_mem_threshold=gpu_mem_threshold,
            gpu_stable_time=gpu_stable_time,
            job_startup_grace=job_startup_grace
        )
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.option('--all', 'all_nodes', is_flag=True, help='Stop all nodes in cluster (head only)')
def stop(all_nodes):
    """Stop scheduler"""
    try:
        code = stop_command(all_nodes=all_nodes)
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command(context_settings=dict(
    ignore_unknown_options=True, 
    allow_extra_args=True,
    allow_interspersed_args=False
))
@click.option('--req', default='1', help='GPU requirements')
@click.option('--depends-on', 'depends_on', multiple=True, help='Job dependencies (job IDs or ^ for previous job, ^^ for 2nd previous, etc.)')
@click.option('--name', help='Job name')
@click.option('--priority', type=int, default=0, help='Priority')
@click.option('--env', multiple=True, help='Environment variables (KEY=VALUE)')
@click.option('--working-dir', help='Working directory for job')
@click.pass_context
def submit(ctx, req, depends_on, name, priority, env, working_dir):
    """Submit a job

    COMMAND can be any command with arguments, e.g.:

    \b
    scheduler submit python train.py --epochs 10
    scheduler submit bash run.sh arg1 arg2
    scheduler submit ./myexec --option value

    Returns immediately after submission (async mode).
    """
    try:
        # Get command from context args (everything after the options)
        command = list(ctx.args)
        code = submit_command(
            command=command,
            req=req,
            depends_on=list(depends_on) if depends_on else None,
            name=name,
            priority=priority,
            env=list(env) if env else None,
            working_dir=working_dir
        )
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command('submit-batch')
@click.argument('script_list')
@click.option('--req', default='1', help='GPU requirements')
@click.option('--depends-on', 'depends_on', multiple=True, help='Job dependencies (job IDs or ^ for previous job, ^^ for 2nd previous, etc.)')
@click.option('--name', help='Job name')
@click.option('--priority', type=int, default=0, help='Priority')
@click.option('--env', multiple=True, help='Environment variables (KEY=VALUE)')
@click.option('--working-dir', help='Working directory for job')
@click.option('--sequential', is_flag=True, help='Each job depends on previous job')
def submit_batch(script_list, req, depends_on, name, priority, env, working_dir, sequential):
    """Submit multiple jobs from a file

    Returns immediately after submitting all jobs (async mode).
    """
    try:
            code = submit_batch_command(
            script_list=script_list,
            req=req,
            depends_on=list(depends_on) if depends_on else None,
            name=name,
            priority=priority,
            env=list(env) if env else None,
            working_dir=working_dir,
            sequential=sequential
        )
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('job_ids', nargs=-1)
@click.option('--format', 'output_format', default='table', type=click.Choice(['table', 'json', 'yaml']), help='Output format')
@click.option('--filter', default='all', help='Filter by status')
@click.option('--limit', type=int, default=50, help='Max jobs')
def jobs(job_ids, output_format, filter, limit):
    """List jobs"""
    try:
            code = jobs_command(
            job_ids=list(job_ids) if job_ids else None,
            format=output_format,
            filter=filter,
            limit=limit
        )
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('job_id')
@click.option('-n', '--lines', type=int, default=100, help='Number of lines')
@click.option('--timestamps', is_flag=True, help='Show timestamps')
@click.option('--stderr', is_flag=True, help='Show stderr')
@click.option('--both', is_flag=True, help='Show both stdout/stderr')
def logs(job_id, lines, timestamps, stderr, both):
    """View job logs"""
    try:
            code = logs_command(
            job_id=job_id,
            lines=lines,
            timestamps=timestamps,
            stderr=stderr,
            both=both
        )
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('job_ids', nargs=-1, required=True)
def cancel(job_ids):
    """Cancel jobs"""
    try:
        code = cancel_command(job_ids=list(job_ids))
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


# Add retry command to CLI
cli.add_command(retry)


@cli.command()
@click.argument('subcommand', type=click.Choice(['init', 'show', 'get', 'set']))
@click.argument('key', required=False)
@click.argument('value', required=False)
@click.option('--config-file', help='Path to configuration file')
def config(subcommand, key, value, config_file):
    """Manage configuration"""
    try:
            code = config_command(
            command=subcommand,
            key=key,
            value=value,
            config_file=config_file
        )
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
def status():
    """Show cluster status (TUI)"""
    try:
            code = status_command()
            sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('target')
@click.option('--failed', is_flag=True, help='Only purge failed jobs')
@click.option('--completed', is_flag=True, help='Only purge completed jobs')
@click.option('--cancelled', is_flag=True, help='Only purge cancelled jobs')
def purge(target, failed, completed, cancelled):
    """Purge jobs by time or job ID

    TARGET can be either:
    - A time duration: 7d, 3w, 24h, 30m (days, weeks, hours, minutes)
    - A specific job ID

    Examples:

    \b
    scheduler purge 7d              # Purge all terminal jobs older than 7 days
    scheduler purge 3w --failed     # Purge failed jobs older than 3 weeks
    scheduler purge 24h --completed # Purge completed jobs older than 24 hours
    scheduler purge job_abc123      # Purge specific job
    """
    try:
        code = purge_command(
            target=target,
            failed=failed,
            completed=completed,
            cancelled=cancelled
        )
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('target')
@click.argument('duration')
def freeze(target, duration):
    """Freeze a GPU for a specified duration

    Prevents jobs from being scheduled on the specified GPU.

    TARGET format: node:GPUx or node:x (e.g., "node1:GPU0" or "node1:0")
    DURATION format: <number><unit> where unit is s/m/h/d/w

    Examples:

    \b
    scheduler freeze node1:GPU0 12h    # Freeze GPU 0 on node1 for 12 hours
    scheduler freeze node1:0 30m       # Freeze GPU 0 on node1 for 30 minutes
    scheduler freeze gpu2:GPU1 2d      # Freeze GPU 1 on gpu2 for 2 days
    """
    try:
        code = freeze_command(target=target, duration=duration)
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


@cli.command()
@click.argument('target', required=False)
def unfreeze(target):
    """Unfreeze GPU(s)

    Allows jobs to be scheduled on the specified GPU(s) again.

    TARGET format: node:GPUx or node:x (e.g., "node1:GPU0" or "node1:0")
    If no target is specified, unfreezes all GPUs.

    Examples:

    \b
    scheduler unfreeze node1:GPU0      # Unfreeze GPU 0 on node1
    scheduler unfreeze node1:0         # Unfreeze GPU 0 on node1
    scheduler unfreeze                 # Unfreeze all GPUs
    """
    try:
        code = unfreeze_command(target=target)
        sys.exit(code)
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        click.echo(f"Error: {e}")
        sys.exit(1)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == '__main__':
    main()