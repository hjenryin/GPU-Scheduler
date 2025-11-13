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


def _cleanup_daemon_logs(log_dir: str, daemon_prefix: str, max_age_hours: int = 24):
    """
    Clean up old log entries from daemon log files before starting daemon.

    This filters out log entries older than max_age_hours, keeping only recent
    entries. This prevents stale log entries from previous runs from accumulating
    while preserving recent logs.

    Since logs are always generated in chronological order, we use binary search
    to efficiently find the first recent entry in O(log n) time.

    Args:
        log_dir: Directory containing log files
        daemon_prefix: Prefix for log files (e.g., 'head' or 'worker-nodename')
        max_age_hours: Maximum age of log entries to keep in hours (default: 24)
    """
    import re
    from datetime import datetime, timedelta

    cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

    def extract_timestamp(line: str):
        """Extract and parse timestamp from log line."""
        # Common format: "2025-11-10 12:34:56,123 - ..." or similar
        timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', line)
        if timestamp_match:
            try:
                timestamp_str = timestamp_match.group(1)
                return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        return None

    # Process both stdout and stderr log files for this daemon
    for log_type in ['stdout', 'stderr']:
        log_file = os.path.join(log_dir, f'{daemon_prefix}-{log_type}.log')

        if not os.path.exists(log_file):
            continue

        try:
            # Read the log file
            with open(log_file, 'r') as f:
                lines = f.readlines()

            if not lines:
                continue

            # Binary search to find first line with timestamp >= cutoff_time
            left, right = 0, len(lines) - 1
            first_recent_idx = None

            while left <= right:
                mid = (left + right) // 2
                timestamp = extract_timestamp(lines[mid])

                if timestamp is None:
                    # No timestamp, search left side to find timestamped entries
                    right = mid - 1
                    continue

                if timestamp >= cutoff_time:
                    # This line is recent, but there might be earlier recent lines
                    first_recent_idx = mid
                    right = mid - 1
                else:
                    # This line is old, search right side
                    left = mid + 1

            # If no recent entries found, remove entire file
            if first_recent_idx is None:
                os.remove(log_file)
                logger.info(f"Removed {daemon_prefix}-{log_type}.log (all entries older than {max_age_hours}h)")
            elif first_recent_idx > 0:
                # Write back only recent entries
                with open(log_file, 'w') as f:
                    f.writelines(lines[first_recent_idx:])
                logger.info(f"Cleaned {first_recent_idx} old log entries from {daemon_prefix}-{log_type}.log")

        except OSError as e:
            logger.warning(f"Failed to clean up daemon log {log_file}: {e}")


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
    from scheduler.core import is_port_available, find_available_port
    
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
            from scheduler.core import HeadConfig
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

    # If non-blocking mode, fork a background process
    if not block:
        return _daemonize_head(config, singleton)
    
    # Blocking mode - run in foreground
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
        
        # Start worker in background thread
        from threading import Thread
        worker_thread = Thread(
            target=lambda: _start_worker_node_internal(worker_config, None, None),
            daemon=True
        )
        worker_thread.start()
        
        # Give worker time to start
        time.sleep(2)

        click.echo("\n✓ Cluster ready (head + worker on this machine)")
        click.echo("\nTo connect worker nodes from other machines, run:")
        click.echo(f"  scheduler start --address {socket.gethostname()}:{config.head.port}")
        click.echo("\nPress Ctrl+C to stop...")
        orchestrator.run()
        # Lock will be released by orchestrator.stop() when run() completes

        return 0
    except KeyboardInterrupt:
        # Ctrl+C was pressed - this is expected
        click.echo("\nShutting down gracefully...")
        # Lock will be released by orchestrator.stop() which was already called
        return 0
    except Exception as e:
        # Only release lock on error
        singleton.release_lock()
        raise


def _daemonize_head(config: Config, singleton: SingletonDaemon) -> int:
    """Fork and daemonize the head node process."""
    import sys
    
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - wait for grandchild PID to be written
            import time
            time.sleep(0.5)
            
            # Read the actual daemon PID from the lockfile
            lockfile_path = os.path.expanduser("~/.scheduler/head.lock")
            try:
                import json
                with open(lockfile_path, 'r') as f:
                    data = json.load(f)
                daemon_pid = data.get('pid')
                click.echo(f"\n✓ Head node started in background (PID: {daemon_pid})")
            except:
                click.echo(f"\n✓ Head node started in background")

            click.echo("Use 'scheduler stop --all' to stop it")
            click.echo("\nTo connect worker nodes from other machines, run:")
            click.echo(f"  scheduler start --address {socket.gethostname()}:{config.head.port}")
            return 0
    except OSError as e:
        click.echo(f"Fork failed: {e}")
        singleton.release_lock()
        return 1
    
    # Child process continues
    # Detach from parent environment
    os.setsid()
    os.umask(0)
    
    # Second fork to prevent zombie
    try:
        pid = os.fork()
        if pid > 0:
            # Exit first child
            sys.exit(0)
    except OSError as e:
        sys.exit(1)
    
    # Grandchild process continues - this is the daemon
    # Update the lockfile with the actual daemon PID
    lockfile_path = os.path.expanduser("~/.scheduler/head.lock")
    try:
        import json
        with open(lockfile_path, 'w') as f:
            json.dump({'pid': os.getpid()}, f)
    except Exception as e:
        logger.error(f"Failed to update lockfile with daemon PID: {e}")
    
    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    # Redirect stdin/stdout/stderr to log files
    log_dir = os.path.expanduser("~/.scheduler/logs")
    os.makedirs(log_dir, exist_ok=True)

    # Clean up old head node log files before opening them
    # This prevents stale logs from accumulating across restarts
    _cleanup_daemon_logs(log_dir, 'head')

    stdin = open('/dev/null', 'r')
    stdout = open(os.path.join(log_dir, 'head-stdout.log'), 'a')
    stderr = open(os.path.join(log_dir, 'head-stderr.log'), 'a')
    
    os.dup2(stdin.fileno(), sys.stdin.fileno())
    os.dup2(stdout.fileno(), sys.stdout.fileno())
    os.dup2(stderr.fileno(), sys.stderr.fileno())
    
    # Now run the head node
    try:
        orchestrator = Orchestrator(config, singleton)
        orchestrator.start()
        
        # Also start a worker on the same machine
        import time
        time.sleep(1)
        
        worker_config = Config(
            address=f"{socket.gethostname()}:{config.head.port}",
            head=config.head,
            worker=config.worker,
            storage=config.storage,
            client=config.client
        )
        
        from threading import Thread
        worker_thread = Thread(
            target=lambda: _start_worker_node_internal(worker_config, None, None),
            daemon=True
        )
        worker_thread.start()
        time.sleep(2)
        
        # Keep daemon alive
        orchestrator.run()
        
        # Clean up lock file when orchestrator exits
        singleton.release_lock()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        singleton.release_lock()
        sys.exit(1)


def _daemonize_worker(config: Config, node_name: str, num_gpus: Optional[int], lockfile_path: str) -> int:
    """Fork and daemonize the worker node process."""
    import sys
    import json

    # Create a status file to communicate startup success/failure
    status_file = os.path.expanduser(f"~/.scheduler/worker-{node_name}.status")

    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - wait for daemon to report status
            import time

            # Wait up to 10 seconds for the daemon to start and report status
            max_wait = 10
            start_time = time.time()

            while time.time() - start_time < max_wait:
                if os.path.exists(status_file):
                    try:
                        with open(status_file, 'r') as f:
                            status_data = json.load(f)

                        if status_data.get('status') == 'running':
                            daemon_pid = status_data.get('pid')
                            click.echo(f"\n✓ Worker node started in background (PID: {daemon_pid})")
                            click.echo("Use 'scheduler stop' to stop it")
                            # Clean up status file
                            try:
                                os.remove(status_file)
                            except:
                                pass
                            return 0
                        elif status_data.get('status') == 'failed':
                            error_msg = status_data.get('error', 'Unknown error')
                            click.echo(f"\n✗ Worker node failed to start: {error_msg}")
                            # Clean up status file
                            try:
                                os.remove(status_file)
                            except:
                                pass
                            return 1
                    except (json.JSONDecodeError, IOError):
                        # File might be partially written, wait a bit more
                        pass

                time.sleep(0.2)

            # Timeout - daemon didn't report status
            click.echo("\n✗ Worker node failed to start: Timeout waiting for daemon status")
            click.echo("Check logs in ~/.scheduler/logs/ for details")
            return 1
    except OSError as e:
        click.echo(f"Fork failed: {e}")
        return 1
    
    # Child process continues
    os.setsid()
    os.umask(0)
    
    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        sys.exit(1)
    
    # Grandchild process - the daemon
    # Now acquire the lock in THIS process (the actual daemon)
    daemon_singleton = SingletonDaemon(lockfile_path)
    if not daemon_singleton.acquire_lock():
        # Another daemon started between our check and fork
        error_msg = f"Worker '{node_name}' is already running"
        try:
            with open(status_file, 'w') as f:
                json.dump({'status': 'failed', 'error': error_msg}, f)
        except Exception:
            pass
        sys.exit(1)

    # Update the lockfile with head address (PID already set by acquire_lock)
    try:
        import json
        with open(lockfile_path, 'r') as f:
            data = json.load(f)
        data['address'] = config.address
        with open(lockfile_path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to update lockfile with head address: {e}")
    
    sys.stdout.flush()
    sys.stderr.flush()

    log_dir = os.path.expanduser("~/.scheduler/logs")
    os.makedirs(log_dir, exist_ok=True)

    # Clean up old worker node log files before opening them
    # This prevents stale logs from accumulating across restarts
    _cleanup_daemon_logs(log_dir, f'worker-{node_name}')

    stdin = open('/dev/null', 'r')
    stdout = open(os.path.join(log_dir, f'worker-{node_name}-stdout.log'), 'a')
    stderr = open(os.path.join(log_dir, f'worker-{node_name}-stderr.log'), 'a')
    
    os.dup2(stdin.fileno(), sys.stdin.fileno())
    os.dup2(stdout.fileno(), sys.stdout.fileno())
    os.dup2(stderr.fileno(), sys.stderr.fileno())
    
    # Run the worker
    try:
        daemon = WorkerDaemon(config, node_name, num_gpus)
        daemon.start()  # Start the daemon (which includes registration)
        
        # If we get here, daemon started successfully
        # Write success status
        try:
            with open(status_file, 'w') as f:
                json.dump({'status': 'running', 'pid': os.getpid()}, f)
        except Exception as status_error:
            logger.error(f"Failed to write status file: {status_error}")
        
        # Continue running
        daemon.run_main_loop()  # Run without calling start() again

        # Clean up lock file when daemon exits
        daemon_singleton.release_lock()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Worker daemon failed: {e}", exc_info=True)

        # Write failure status
        try:
            error_msg = str(e)
            # Extract more user-friendly error message
            if "Failed to register with head node" in error_msg:
                if "Failed to resolve" in error_msg or "Name resolution" in error_msg:
                    error_msg = f"Cannot resolve head node address '{config.address}'"
                elif "Connection refused" in error_msg:
                    error_msg = f"Cannot connect to head node at '{config.address}' (connection refused)"
                else:
                    error_msg = f"Cannot connect to head node at '{config.address}'"

            with open(status_file, 'w') as f:
                json.dump({'status': 'failed', 'error': error_msg}, f)
        except Exception as status_error:
            logger.error(f"Failed to write status file: {status_error}")

        daemon_singleton.release_lock()
        sys.exit(1)


def _start_worker_node_internal(config: Config, node_name: Optional[str], num_gpus: Optional[int]) -> None:
    """Start worker node internally (used by head node to start local worker)."""
    if not node_name:
        node_name = socket.gethostname()

    # Set up separate logging for the worker thread
    # This prevents worker logs from going to the head log file
    log_dir = os.path.expanduser("~/.scheduler/logs")
    os.makedirs(log_dir, exist_ok=True)

    worker_log_file = os.path.join(log_dir, f'worker-{node_name}-stdout.log')
    worker_handler = logging.FileHandler(worker_log_file)
    worker_handler.setLevel(logging.INFO)
    worker_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    worker_handler.setFormatter(worker_formatter)

    # Add filter to only capture worker-related logs
    class WorkerFilter(logging.Filter):
        def filter(self, record):
            # Only capture logs from scheduler.worker modules
            return record.name.startswith('scheduler.worker')

    worker_handler.addFilter(WorkerFilter())

    # Add handler to root logger (will be removed in finally block)
    root_logger = logging.getLogger()
    root_logger.addHandler(worker_handler)

    # Check for existing worker
    os.makedirs(os.path.expanduser("~/.scheduler"), exist_ok=True)
    lockfile = os.path.expanduser(f"~/.scheduler/worker-{node_name}.lock")
    singleton = SingletonDaemon(lockfile)

    if not singleton.acquire_lock():
        logger.warning(f"Worker '{node_name}' is already running, skipping local worker start")
        root_logger.removeHandler(worker_handler)
        worker_handler.close()
        return

    # Save head address to lockfile AFTER acquiring lock
    try:
        import json
        with open(lockfile, 'w') as f:
            json.dump({'pid': os.getpid(), 'address': config.address}, f)
    except Exception as e:
        logger.warning(f"Failed to save head address to lockfile: {e}")

    try:
        daemon = WorkerDaemon(config, node_name, num_gpus)
        daemon.run()
    finally:
        singleton.release_lock()
        # Clean up the worker log handler
        root_logger.removeHandler(worker_handler)
        worker_handler.close()


def _start_worker_node(config: Config, node_name: Optional[str], num_gpus: Optional[int], block: bool) -> int:
    """Start worker node daemon."""
    from scheduler.core import save_head_info

    # Determine node name
    if not node_name:
        node_name = socket.gethostname()

    click.echo(f"Starting scheduler as WORKER NODE...")
    click.echo(f"Node name: {node_name}")

    # Display connection info
    click.echo(f"Connecting to head node: {config.address}")

    # Check for existing worker
    # Use hardcoded location for lock files as documented
    os.makedirs(os.path.expanduser("~/.scheduler"), exist_ok=True)
    lockfile_path = os.path.expanduser(f"~/.scheduler/worker-{node_name}.lock")

    # Check if already running (don't acquire lock yet for daemon mode)
    from scheduler.worker import is_daemon_running
    if is_daemon_running(lockfile_path):
        click.echo(f"\nError: Worker '{node_name}' is already running on this machine")
        click.echo("Use 'scheduler stop' to stop it first")
        return 1

    # If non-blocking mode, fork a background process
    # The daemon process will acquire the lock after forking
    if not block:
        return _daemonize_worker(config, node_name, num_gpus, lockfile_path)
    
    # Blocking mode - run in foreground
    # Acquire lock in this process
    singleton = SingletonDaemon(lockfile_path)
    if not singleton.acquire_lock():
        click.echo(f"\nError: Worker '{node_name}' is already running on this machine")
        click.echo("Use 'scheduler stop' to stop it first")
        return 1

    try:
        daemon = WorkerDaemon(config, node_name, num_gpus)
        click.echo("\nWorker node started. Press Ctrl+C to stop.")
        daemon.run()
        return 0
    except KeyboardInterrupt:
        # Ctrl+C was pressed - this is expected
        click.echo("\nShutting down gracefully...")
        # daemon.stop() was already called in daemon.run()'s finally block
        return 0
    finally:
        singleton.release_lock()
