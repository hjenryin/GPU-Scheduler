import os
import sys
import socket
import logging
from typing import Optional

from scheduler.core import load_config, save_config, ValidationException, ConnectionException, PermissionDeniedException, constants
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
        print("Error: Must specify either --head or --address")
        print("Usage:")
        print("  Start head node:   scheduler start --head")
        print("  Start worker node: scheduler start --address=<head-address>")
        return 2

    if head and address:
        print("Warning: --address ignored when starting as head node")

    # Load or create configuration
    try:
        config = load_config()
    except:
        config = {}

    # Update config with CLI arguments
    if temp_dir:
        config.setdefault('worker', {})['work_dir'] = os.path.expanduser(temp_dir)
    if log_dir:
        config.setdefault('worker', {})['log_dir'] = os.path.expanduser(log_dir)

    # Merge kwargs into config
    if head:
        config.setdefault('head_node', {})['port'] = port
        for key, value in kwargs.items():
            if key.startswith('heartbeat_') or key.startswith('scheduling_'):
                config['head_node'][key] = value
    else:
        config.setdefault('head_node', {})['host'] = address.split(':')[0] if ':' in address else address
        if ':' in address:
            config['head_node']['port'] = int(address.split(':')[1])

        for key, value in kwargs.items():
            if key.startswith('gpu_') or key.startswith('job_'):
                config.setdefault('worker', {})[key] = value

    try:
        if head:
            return _start_head_node(config, block)
        else:
            return _start_worker_node(config, node_name, num_gpus, block)
    except ValidationException as e:
        print(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        print(f"Connection error: {e}")
        print("\nTroubleshooting:")
        print("  - Verify head node is running")
        print("  - Check network connectivity")
        print(f"  - Test with: curl http://{address}/api/v1/health")
        return 3
    except PermissionDeniedException as e:
        print(f"Permission error: {e}")
        print("\nTroubleshooting:")
        print("  - Port may already be in use")
        print("  - Try a different port with --port")
        print("  - Check for existing scheduler process")
        return 5
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"Error: {e}")
        return 1


def _start_head_node(config: dict, block: bool) -> int:
    """Start head node orchestrator."""
    print("Starting scheduler as HEAD NODE...")
    print(f"Port: {config.get('head_node', {}).get('port', constants.DEFAULT_PORT)}")
    print(f"API: http://localhost:{config.get('head_node', {}).get('port', constants.DEFAULT_PORT)}/api/v1")

    # Check for existing head node
    lockfile = os.path.expanduser("~/.scheduler/head.lock")
    singleton = SingletonDaemon(lockfile)

    if not singleton.acquire_lock():
        print("\nError: Head node is already running on this machine")
        print("Use 'scheduler stop' to stop it first")
        return 1

    try:
        orchestrator = Orchestrator(config)

        if block:
            print("\nHead node started. Press Ctrl+C to stop.")
            print("Workers can connect with: scheduler start --address=<this-host>:<port>")
            orchestrator.run()
        else:
            orchestrator.start()
            print("\nHead node started in background")
            print("Use 'scheduler stop' to stop it")

        return 0
    finally:
        singleton.release_lock()


def _start_worker_node(config: dict, node_name: Optional[str], num_gpus: Optional[int], block: bool) -> int:
    """Start worker node daemon."""
    # Determine node name
    if not node_name:
        node_name = socket.gethostname()

    print(f"Starting scheduler as WORKER NODE...")
    print(f"Node name: {node_name}")

    head_host = config.get('head_node', {}).get('host', 'localhost')
    head_port = config.get('head_node', {}).get('port', constants.DEFAULT_PORT)
    print(f"Connecting to head node: {head_host}:{head_port}")

    # Check for existing worker
    lockfile = os.path.expanduser(f"~/.scheduler/worker-{node_name}.lock")
    singleton = SingletonDaemon(lockfile)

    if not singleton.acquire_lock():
        print(f"\nError: Worker '{node_name}' is already running on this machine")
        print("Use 'scheduler stop' to stop it first")
        return 1

    try:
        daemon = WorkerDaemon(config, node_name, num_gpus)

        if block:
            print("\nWorker node started. Press Ctrl+C to stop.")
            daemon.run()
        else:
            daemon.start()
            print("\nWorker node started in background")
            print("Use 'scheduler stop' to stop it")

        return 0
    finally:
        singleton.release_lock()
