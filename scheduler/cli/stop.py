import os
import signal
import logging
import time
import click

from scheduler.worker import is_daemon_running
from scheduler.core import load_config
from scheduler.api import SchedulerClient
from scheduler.core import ConnectionException

logger = logging.getLogger(__name__)


def stop_command(all_nodes: bool = False, no_wait: bool = False) -> int:
    """
    Stop scheduler on current node or all nodes.

    Args:
        all_nodes: If True, stop all nodes in cluster (head only)
        no_wait: If True, skip waiting for workers to shut down

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to scheduler
    """
    if all_nodes:
        return _stop_all_nodes(no_wait=no_wait)
    
    # Check if head node is running (for warning)
    scheduler_dir = os.path.expanduser("~/.scheduler")
    head_lockfile = os.path.join(scheduler_dir, "head.lock")
    head_running = is_daemon_running(head_lockfile)
    
    # Try to stop worker nodes (check common lock patterns)
    worker_stopped = False
    if os.path.exists(scheduler_dir):
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".lock"):
                lockfile = os.path.join(scheduler_dir, filename)
                node_name = filename[7:-5]  # Remove "worker-" and ".lock"
                if _stop_daemon(lockfile, f"worker node '{node_name}'"):
                    worker_stopped = True

    if not worker_stopped:
        click.echo("No worker processes found running on this machine")
        return 1

    # Warn if head is also running
    if head_running:
        click.echo("\n⚠ Warning: Head node is still running on this machine")
        click.echo("To stop the head node, run: scheduler stop --all")

    return 0


def _stop_all_nodes(no_wait: bool = False) -> int:
    """
    Stop all nodes in the cluster.

    This function:
    1. Detects if running from head node or worker node
    2. If from head: directly stops all nodes locally
    3. If from worker: calls head node's cluster shutdown API

    Args:
        no_wait: If True, skip waiting for workers to shut down

    Returns:
        Exit code (0 for success)
    """
    try:
        # Detect if we're running on the head node FIRST
        # This avoids needing to connect to the API when running locally
        is_head_node = _is_running_on_head_node()
        
        if is_head_node:
            # Running from head node - request cluster shutdown via API
            # This will signal ALL workers (including local ones) to shut down immediately
            click.echo("✓ Shutting down entire cluster...")
            
            # Request cluster shutdown via the API to signal all workers
            try:
                config = load_config()
                client = SchedulerClient(config=config)
                
                # Get list of all nodes to show what we're shutting down
                try:
                    nodes = client.list_nodes()
                    if nodes:
                        click.echo(f"Found {len(nodes)} worker nodes in cluster")
                except:
                    pass  # Continue even if we can't list nodes
                
                # Request cluster shutdown to signal all workers
                try:
                    client.shutdown_cluster(graceful_timeout=60, force=False)
                    click.echo("✓ Shutdown signal sent to all workers")
                    # Give workers time to receive the signal and shut down (15+ seconds)
                    # This matches the timeout in the orchestrator
                    if not no_wait:
                        click.echo("Waiting for workers to receive shutdown signal...")
                        time.sleep(16)  # Wait slightly longer than orchestrator's 15s timeout
                    else:
                        click.echo("⚠ Skipping wait - workers will shut down asynchronously")
                except Exception as e:
                    logger.warning(f"Could not signal workers: {e}")
                    click.echo("⚠ Could not signal workers via API")
                    
                    # Fallback: try to stop local workers directly if API call failed
                    worker_stopped = _stop_local_worker_nodes()
                    if worker_stopped:
                        click.echo("✓ Local worker nodes stopped successfully")
            except Exception as e:
                logger.warning(f"Could not connect to head API: {e}")
                # Fallback: stop local workers directly if can't connect to API
                worker_stopped = _stop_local_worker_nodes()
                if worker_stopped:
                    click.echo("✓ Local worker nodes stopped successfully")
            
            # The head node should have stopped itself via the API shutdown
            # But if it's still running, stop it manually
            head_lockfile = os.path.expanduser("~/.scheduler/head.lock")
            if os.path.exists(head_lockfile):
                click.echo("✓ Head node stopped itself")
            else:
                click.echo("⚠ Head node not found (may have already stopped)")
            
            click.echo("✓ Cluster shutdown completed")
            return 0
        
        # Running from worker node - need to connect to head node API
        # Load configuration to get head node address
        config = load_config()
        
        # Create client (will auto-detect address from worker lock or config)
        client = SchedulerClient(config=config)
        
        # Get list of all nodes
        nodes = client.list_nodes()
        
        if not nodes:
            click.echo("No nodes found in cluster")
            return 1
            
        click.echo(f"Found {len(nodes)} nodes in cluster:")
        
        # Display all nodes
        for node in nodes:
            status = "connected" if node.status.value == "connected" else "disconnected"
            click.echo(f"  - {node.node_name} ({node.address}) - {status}")
        
        # Running from worker node - request cluster shutdown from head
        click.echo("\n✓ Requesting cluster shutdown from head node...")
        
        try:
            success = client.shutdown_cluster(graceful_timeout=60, force=False)
            if success:
                click.echo("✓ Cluster shutdown initiated successfully")

                if not no_wait:
                    click.echo("Waiting for all workers to receive shutdown signal...")
                    # Wait for workers to receive shutdown signal and stop
                    # This matches the orchestrator's wait time
                    time.sleep(16)  # Wait slightly longer than orchestrator's 15s timeout
                    click.echo("✓ All workers should have stopped")
                else:
                    click.echo("⚠ Skipping wait - workers will shut down asynchronously")
                    click.echo("Workers will stop within 10-20 seconds via heartbeat mechanism")

                # Note: The current worker will also stop via the heartbeat mechanism
                # No need to manually stop it
            else:
                click.echo("⚠ Cluster shutdown request failed")
                return 1
                
        except ConnectionException as e:
            click.echo(f"Error: Cannot request cluster shutdown: {e}")
            click.echo("Make sure the head node is running and accessible")
            return 1
        
        return 0
        
    except ConnectionException as e:
        click.echo(f"Error: Cannot connect to head node: {e}")
        click.echo("Make sure the head node is running and accessible")
        return 1
    except Exception as e:
        logger.error(f"Error stopping all nodes: {e}")
        click.echo(f"Error: {e}")
        return 1


def _is_running_on_head_node() -> bool:
    """
    Detect if we're running on the head node.
    
    Returns:
        True if running on head node, False if running on worker node
    """
    # Check if head lockfile exists locally
    scheduler_dir = os.path.expanduser("~/.scheduler")
    head_lockfile = os.path.join(scheduler_dir, "head.lock")
    return os.path.exists(head_lockfile) and is_daemon_running(head_lockfile)


def _stop_local_worker_nodes() -> bool:
    """
    Stop all local worker nodes.
    
    Returns:
        True if any worker nodes were stopped, False if none were running
    """
    worker_stopped = False
    scheduler_dir = os.path.expanduser("~/.scheduler")
    if os.path.exists(scheduler_dir):
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".lock"):
                lockfile = os.path.join(scheduler_dir, filename)
                node_name = filename[7:-5]  # Remove "worker-" and ".lock"
                if _stop_daemon(lockfile, f"worker node '{node_name}'"):
                    worker_stopped = True
    return worker_stopped


def _stop_daemon(lockfile: str, name: str) -> bool:
    """
    Stop a daemon by reading its PID from lockfile.

    Returns:
        True if daemon was stopped, False if not running
    """
    if not is_daemon_running(lockfile):
        return False

    try:
        import json
        with open(lockfile, 'r') as f:
            data = json.load(f)
        
        pid = data.get('pid')
        if not pid:
            return False

        click.echo(f"Stopping {name} (PID {pid})...")
        os.kill(pid, signal.SIGTERM)
        click.echo(f"Sent shutdown signal to {name}")
        click.echo("(Running jobs will be left running and marked as untracked)")

        # Clean up lockfile
        try:
            os.remove(lockfile)
        except OSError as e:
            logger.warning(f"Failed to remove lockfile {lockfile}: {e}")

        return True
    except (ValueError, ProcessLookupError, PermissionError, KeyError, json.JSONDecodeError) as e:
        logger.warning(f"Failed to stop {name}: {e}")
        # Try to clean up stale lockfile
        try:
            os.remove(lockfile)
        except OSError as e:
            logger.warning(f"Failed to remove stale lockfile {lockfile}: {e}")
        return False
