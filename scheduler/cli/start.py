import os
import sys
import socket
import logging
from typing import Optional
import click

from scheduler.core import Config, load_config, ValidationException, ConnectionException, PermissionDeniedException, constants
from scheduler.head import Orchestrator
from scheduler.worker import WorkerDaemon, SingletonDaemon

logger = logging.getLogger(__name__)


def start_command(
    head: bool = False,
    address: Optional[str] = None,
    port: int = constants.DEFAULT_PORT,
    node_name: Optional[str] = None,
    num_gpus: Optional[int] = None,
    temp_dir: Optional[str] = None,
    log_dir: Optional[str] = None,
    block: bool = True,
    log_level: str = "INFO",
    **kwargs
) -> int:
    """
    Start scheduler as head node or worker node.

    Args:
        head: If True, start as head node
        address: Head node address (for worker nodes)
        port: Port for head node
        node_name: Name for this node
        num_gpus: Number of GPUs (auto-detect if None)
        temp_dir: Temporary directory path
        log_dir: Log directory path
        block: If True, block until stopped
        log_level: Logging level
        **kwargs: Additional head/worker specific options

    Returns:
        Exit code (0 for success)

    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node (worker)
        PermissionDeniedException: If cannot bind to port (head)
    """
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Validate arguments
    if not head and not address:
        click.echo("Error: Must specify either --head or --address")
        click.echo("Usage:")
        click.echo("  Start head node:   scheduler start --head")
        click.echo("  Start worker node: scheduler start --address=<head-address>")
        return 2

    if head and address:
        click.echo("Warning: --address ignored when starting as head node")

    # Load base configuration
    try:
        base_config = load_config()
    except Exception as e:
        logger.warning(f"Failed to load config file, using defaults: {e}")
        base_config = Config()

    # Build config dict for customization
    config_dict = base_config.to_dict()

    # Update with CLI arguments
    if temp_dir:
        config_dict.setdefault('worker', {})['work_dir'] = os.path.expanduser(temp_dir)
    if log_dir:
        config_dict.setdefault('worker', {})['log_dir'] = os.path.expanduser(log_dir)

    # Merge kwargs and set address
    if head:
        config_dict.setdefault('head', {})['port'] = port
        for key, value in kwargs.items():
            if key.startswith('heartbeat_') or key.startswith('scheduling_') or key.startswith('graceful_shutdown_'):
                if value is not None:  # Only set if value is not None
                    config_dict.setdefault('head', {})[key] = value
    else:
        # For worker, set the address field to connect to head
        config_dict['address'] = address
        for key, value in kwargs.items():
            if key.startswith('gpu_') or key.startswith('job_'):
                if value is not None:  # Only set if value is not None
                    config_dict.setdefault('worker', {})[key] = value

    # Create final Config object from customized dict
    config = Config.from_dict(config_dict)

    try:
        if head:
            return _start_head_node(config, block)
        else:
            return _start_worker_node(config, node_name, num_gpus, block)
    except ValidationException as e:
        click.echo(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        click.echo(f"Connection error: {e}")
        click.echo("\nTroubleshooting:")
        click.echo("  - Verify head node is running")
        click.echo("  - Check network connectivity")
        click.echo(f"  - Test with: curl http://{address}/api/v1/health")
        return 3
    except PermissionDeniedException as e:
        click.echo(f"Permission error: {e}")
        click.echo("\nTroubleshooting:")
        click.echo("  - Port may already be in use")
        click.echo("  - Try a different port with --port")
        click.echo("  - Check for existing scheduler process")
        return 5
    except KeyboardInterrupt:
        click.echo("\nShutting down gracefully...")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        click.echo(f"Error: {e}")
        return 1


def _start_head_node(config: Config, block: bool) -> int:
    """Start head node orchestrator."""
    from scheduler.core.utils import is_port_available, find_available_port
    
    click.echo("Starting scheduler as HEAD NODE...")
    
    # Check if the configured port is available
    original_port = config.head.port
    if not is_port_available(original_port):
        click.echo(f"Port {original_port} is already in use by another process")
        click.echo("Searching for an available port...")
        
        try:
            # Find an available port starting from the configured port
            available_port = find_available_port(start_port=original_port, max_attempts=50)
            click.echo(f"Using available port: {available_port}")
            
            # Create a new config with the available port
            from scheduler.core.config import HeadConfig
            new_head_config = HeadConfig(
                port=available_port,
                heartbeat_timeout=config.head.heartbeat_timeout,
                scheduling_interval=config.head.scheduling_interval,
                graceful_shutdown_timeout=config.head.graceful_shutdown_timeout
            )
            config = Config(
                address=f"localhost:{available_port}",
                head=new_head_config,
                worker=config.worker,
                storage=config.storage,
                client=config.client
            )
        except PermissionDeniedException:
            click.echo(f"Error: No available ports found starting from {original_port}")
            click.echo("Please free up some ports or specify a different port with --port")
            return 5
    
    click.echo(f"Port: {config.head.port}")
    click.echo(f"API: http://localhost:{config.head.port}/api/v1")

    # Check for existing head node
    # Use hardcoded location for lock files as documented
    os.makedirs(os.path.expanduser("~/.scheduler"), exist_ok=True)
    lockfile = os.path.expanduser("~/.scheduler/head.lock")
    singleton = SingletonDaemon(lockfile)

    if not singleton.acquire_lock():
        click.echo("\nError: Head node is already running on this machine")
        click.echo("Use 'scheduler stop' to stop it first")
        return 1

    try:
        orchestrator = Orchestrator(config, singleton)

        # Start the head
        orchestrator.start()
        click.echo("\nHead node started successfully")
        
        # Also start a worker on the same machine
        import time
        time.sleep(1)  # Give head a moment to start
        
        click.echo("Starting worker on this machine...")
        
        # Create worker config pointing to this head
        worker_config = Config(
            address=f"{socket.gethostname()}:{config.head.port}",
            head=config.head,
            worker=config.worker,
            storage=config.storage,
            client=config.client
        )
        
        # Start worker in background
        from threading import Thread
        worker_thread = Thread(
            target=lambda: _start_worker_node(worker_config, None, None, block=False),
            daemon=True
        )
        worker_thread.start()
        
        # Give worker time to start
        time.sleep(2)

        if block:
            click.echo("\n✓ Cluster ready (head + worker on this machine)")
            click.echo("Press Ctrl+C to stop...")
            orchestrator.run()
            # Lock will be released by orchestrator.stop() when run() completes
        else:
            click.echo("\n✓ Cluster ready (head + worker on this machine)")
            click.echo("Use 'scheduler stop --all' to stop it")
            # Don't release lock here - orchestrator will manage it via signal handlers
            # The singleton lock will be released when the orchestrator stops

        return 0
    except Exception as e:
        # Only release lock on error
        singleton.release_lock()
        raise


def _start_worker_node(config: Config, node_name: Optional[str], num_gpus: Optional[int], block: bool) -> int:
    """Start worker node daemon."""
    from scheduler.core.head_info import save_head_info
    
    # Determine node name
    if not node_name:
        node_name = socket.gethostname()

    click.echo(f"Starting scheduler as WORKER NODE...")
    click.echo(f"Node name: {node_name}")

    # Display connection info
    click.echo(f"Connecting to head node: {config.address}")
    
    # Save head node address for CLI commands
    save_head_info(config.address)

    # Check for existing worker
    # Use hardcoded location for lock files as documented
    os.makedirs(os.path.expanduser("~/.scheduler"), exist_ok=True)
    lockfile = os.path.expanduser(f"~/.scheduler/worker-{node_name}.lock")
    singleton = SingletonDaemon(lockfile)

    if not singleton.acquire_lock():
        click.echo(f"\nError: Worker '{node_name}' is already running on this machine")
        click.echo("Use 'scheduler stop' to stop it first")
        return 1

    try:
        daemon = WorkerDaemon(config, node_name, num_gpus)

        if block:
            click.echo("\nWorker node started. Press Ctrl+C to stop.")
            daemon.run()
        else:
            daemon.start()
            click.echo("\nWorker node started in background")
            click.echo("Use 'scheduler stop' to stop it")

        return 0
    finally:
        singleton.release_lock()
