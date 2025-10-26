import os
import signal
import logging
import click

from scheduler.worker import is_daemon_running

logger = logging.getLogger(__name__)


def stop_command(all_nodes: bool = False) -> int:
    """
    Stop scheduler on current node or all nodes.

    Args:
        all_nodes: If True, stop all nodes in cluster (head only)

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to scheduler
    """
    if all_nodes:
        click.echo("Error: --all flag not yet implemented")
        click.echo("Please stop each node individually with 'scheduler stop'")
        return 1

    # Try to stop head node
    head_lockfile = os.path.expanduser("~/.scheduler/head.lock")
    head_stopped = _stop_daemon(head_lockfile, "head node")

    # Try to stop worker nodes (check common lock patterns)
    worker_stopped = False
    scheduler_dir = os.path.expanduser("~/.scheduler")
    if os.path.exists(scheduler_dir):
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".lock"):
                lockfile = os.path.join(scheduler_dir, filename)
                node_name = filename[7:-5]  # Remove "worker-" and ".lock"
                if _stop_daemon(lockfile, f"worker node '{node_name}'"):
                    worker_stopped = True

    if not head_stopped and not worker_stopped:
        click.echo("No scheduler processes found running on this machine")
        return 1

    return 0


def _stop_daemon(lockfile: str, name: str) -> bool:
    """
    Stop a daemon by reading its PID from lockfile.

    Returns:
        True if daemon was stopped, False if not running
    """
    if not is_daemon_running(lockfile):
        return False

    try:
        with open(lockfile, 'r') as f:
            pid = int(f.read().strip())

        click.echo(f"Stopping {name} (PID {pid})...")
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent graceful shutdown signal to {name}")
        click.echo("(Jobs will complete before shutdown)")

        # Clean up lockfile
        try:
            os.remove(lockfile)
        except OSError as e:
            logger.warning(f"Failed to remove lockfile {lockfile}: {e}")

        return True
    except (ValueError, ProcessLookupError, PermissionError) as e:
        logger.warning(f"Failed to stop {name}: {e}")
        # Try to clean up stale lockfile
        try:
            os.remove(lockfile)
        except OSError as e:
            logger.warning(f"Failed to remove stale lockfile {lockfile}: {e}")
        return False
