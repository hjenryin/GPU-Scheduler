import logging
import signal
import time
import threading
import subprocess
import tempfile
import os
from datetime import datetime
from typing import Optional

from scheduler.core import Config, PermissionDeniedException, ShutdownState
from scheduler.storage import FileBackend, SQLiteBackend
from scheduler.manager import PersistenceManager, JobManager, NodeManager, Scheduler
from scheduler.head.api_server import APIServer
from scheduler.worker import FileHandler

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main head node orchestrator with singleton pattern"""

    # Class-level singleton instance
    _instance: Optional['Orchestrator'] = None
    _lock = threading.Lock()

    def __init__(self, config: Config, singleton=None):
        """
        Initialize orchestrator.

        Args:
            config: Configuration instance
            singleton: SingletonDaemon instance for lock management
        """
        # Store instance at class level (thread-safe)
        with Orchestrator._lock:
            Orchestrator._instance = self

        self.config = config
        self.singleton = singleton
        self.running = False
        self.scheduler_thread: Optional[threading.Thread] = None

        # rsync daemon for log syncing
        self.rsync_daemon_process: Optional[subprocess.Popen] = None
        self.rsync_config_file: Optional[str] = None
        self.rsync_port: Optional[int] = None  # Actual port in use, None if unavailable

        # Initialize storage backend
        if config.storage.backend == 'sqlite':
            backend = SQLiteBackend(config.storage.db_path)
            logger.info(f"Using SQLite backend at {config.storage.db_path}")
        else:
            backend = FileBackend(config.storage.data_dir)
            logger.info(f"Using file backend at {config.storage.data_dir}")

        # Initialize persistence layer
        persistence = PersistenceManager(backend, config)

        # Initialize managers
        self.job_manager = JobManager(persistence, config)
        self.node_manager = NodeManager(persistence, config)

        # Initialize scheduler
        self.scheduler = Scheduler(
            self.job_manager,
            self.node_manager,
            config
        )

        # Initialize API server
        self.api_server = APIServer(self.job_manager, self.node_manager, config)

        # Cleanup old system logs on startup (older than 24 hours)
        # Head node cleans up logs in case it's also running a worker
        # Note: Job logs are NOT cleaned automatically - only via explicit purge commands
        logger.info("Cleaning up old system log files on startup...")
        file_handler = FileHandler(config)
        removed_count = file_handler.cleanup_old_logs(max_age_hours=24, include_job_logs=False)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old system log files on startup")

        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("Orchestrator initialized")

    @classmethod
    def get_instance(cls) -> Optional['Orchestrator']:
        """
        Get the current orchestrator instance.

        Returns:
            The orchestrator instance, or None if not initialized
        """
        with cls._lock:
            return cls._instance

    @classmethod
    def clear_instance(cls):
        """
        Clear the orchestrator instance. Mainly for testing.
        """
        with cls._lock:
            cls._instance = None

    def start(self):
        """
        Start the orchestrator and all components.

        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        if self.running:
            logger.warning("Orchestrator is already running")
            return

        logger.info("Starting orchestrator...")

        # Start API server
        try:
            self.api_server.start()
        except PermissionDeniedException as e:
            logger.error(f"Failed to start API server: {e}")
            raise

        # Start scheduler in a separate thread
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

        # Start rsync daemon for log syncing
        try:
            self._start_rsync_daemon()
        except Exception as e:
            logger.error(f"Failed to start rsync daemon: {e}")
            # Don't fail orchestrator startup if rsync daemon fails
            logger.warning("Continuing without rsync daemon - log syncing will not work")

        logger.info("Orchestrator started successfully")

    def stop(self):
        """
        Stop the orchestrator and all components immediately.
        """
        if not self.running:
            logger.warning("Orchestrator is not running")
            return

        logger.info("Stopping orchestrator...")

        # Signal scheduler to stop
        self.running = False

        # Stop scheduler thread
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        # Stop API server
        self.api_server.stop()

        # Stop rsync daemon
        self._stop_rsync_daemon()

        logger.info("Orchestrator stopped")
        
        # Release singleton lock if we have one
        if self.singleton:
            self.singleton.release_lock()

    def keep_alive_loop(self):
        """
        Keep the orchestrator main thread alive (blocking).
        """
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.stop()
            # Re-raise to propagate to parent context
            raise

    def get_status(self) -> dict:
        """
        Get overall cluster status.

        Returns:
            Dictionary containing cluster status
        """
        nodes = self.node_manager.get_connected_nodes()
        all_jobs = self.job_manager.list_jobs()

        # Count jobs by status
        pending_jobs = [j for j in all_jobs if j.status.value == 'pending']
        running_jobs = [j for j in all_jobs if j.status.value == 'running']
        completed_jobs = [j for j in all_jobs if j.status.value == 'completed']
        failed_jobs = [j for j in all_jobs if j.status.value == 'failed']

        # Count GPUs
        total_gpus = sum(node.num_gpus for node in nodes)
        free_gpus = sum(len(node.get_free_gpus(
            self.config.worker.gpu_util_threshold,
            self.config.worker.gpu_mem_threshold,
            self.config.worker.gpu_stable_time
        )) for node in nodes)
        used_gpus = total_gpus - free_gpus

        return {
            'running': self.running,
            'nodes': {
                'total': len(nodes),
                'connected': len([n for n in nodes if n.status.value == 'connected'])
            },
            'gpus': {
                'total': total_gpus,
                'free': free_gpus,
                'used': used_gpus
            },
            'jobs': {
                'total': len(all_jobs),
                'pending': len(pending_jobs),
                'running': len(running_jobs),
                'completed': len(completed_jobs),
                'failed': len(failed_jobs)
            }
        }

    def _do_scheduler_cycle(self):
        """Execute one scheduler cycle - testable business logic."""
        logger.debug("Running scheduler cycle...")
        # Run scheduler cycle
        self.scheduler.schedule_cycle()

        # Check for node timeouts
        self.node_manager.check_timeouts()

        # Check and restart rsync daemon if it died
        self._check_rsync_daemon()

    def _scheduler_loop(self):
        """Internal scheduler loop thread."""
        logger.info("Scheduler loop started")

        while self.running:
            try:
                self._do_scheduler_cycle()

                # Sleep for schedule interval
                logger.debug(f"Sleeping for {self.config.head.scheduling_interval} seconds")
                time.sleep(self.config.head.scheduling_interval)
            except KeyboardInterrupt:
                logger.info("Received keyboard interrupt in scheduler loop")
                break  # Exit the loop gracefully
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                try:
                    time.sleep(1)  # Brief pause before retrying
                except KeyboardInterrupt:
                    logger.info("Received keyboard interrupt during retry sleep")
                    break  # Exit the loop gracefully

        logger.info("Scheduler loop stopped")

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        
        # This handler is triggered by direct signals (e.g. CLI 'scheduler stop', kill command)
        # It performs a "Head-Only Stop" where workers are NOT signalled to shutdown.
        if self.running:
            logger.info("Stopping head node only (workers will remain running and enter retry loop)")
            self.stop()
            
        # Re-raise KeyboardInterrupt to allow proper cleanup in parent contexts
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()

    def shutdown_cluster_workers(self) -> bool:
        """
        Shutdown all workers and wait for confirmation.
        Does NOT stop the head - caller is responsible for that.

        Returns:
            True if all workers confirmed, False if timeout
        """
        logger.info("Starting cluster shutdown")

        # 1. Untrack running jobs
        running_jobs = self.job_manager.get_running_jobs()
        logger.info(f"Marking {len(running_jobs)} running jobs as untracked")
        for job in running_jobs:
            try:
                self.job_manager.untrack_job(job.job_id)
            except Exception as e:
                logger.error(f"Failed to untrack job {job.job_id}: {e}")

        # 2. Cancel pending jobs
        pending_jobs = self.job_manager.get_pending_jobs()
        logger.info(f"Cancelling {len(pending_jobs)} pending jobs")
        for job in pending_jobs:
            try:
                self.job_manager.cancel_job(job.job_id)
            except Exception as e:
                logger.error(f"Failed to cancel job {job.job_id}: {e}")

        # 3. Signal all workers (sets shutdown_state=PENDING)
        self.node_manager.request_shutdown_all_workers()
        logger.info("Shutdown signal sent to all workers")

        # 4. Wait for all workers to CONFIRM
        # With long-polling, workers will respond almost immediately (<1s)
        # But give 2x heartbeat interval as safety margin
        max_wait = 2 * self.config.worker.heartbeat_interval
        start_time = time.time()

        logger.info(f"Waiting for workers to confirm shutdown (max {max_wait}s)...")
        while time.time() - start_time < max_wait:
            nodes = self.node_manager.get_connected_nodes()
            if not nodes:
                logger.info("No connected nodes to shutdown")
                return True

            if all(node.shutdown_state == ShutdownState.CONFIRMED for node in nodes):
                elapsed = time.time() - start_time
                logger.info(f"All {len(nodes)} workers confirmed shutdown in {elapsed:.1f}s")
                return True

            time.sleep(0.5)

        # Timeout
        nodes = self.node_manager.get_connected_nodes()
        unconfirmed = [n.node_name for n in nodes if n.shutdown_state != ShutdownState.CONFIRMED]
        if unconfirmed:
            logger.warning(f"Workers did not confirm shutdown: {unconfirmed}")

        return False

    def _start_rsync_daemon(self):
        """Start rsync daemon as subprocess for log syncing (no sudo required)."""
        from scheduler.core import RSYNC_PORT, is_port_available

        # Try to find an available port, starting with the default
        # If default port is in use, try the next 10 ports
        available_port = None
        for port_offset in range(11):  # Try ports 8873-8883
            candidate_port = RSYNC_PORT + port_offset
            if is_port_available(candidate_port):
                available_port = candidate_port
                break

        if available_port is None:
            logger.error(f"Cannot start rsync daemon: ports {RSYNC_PORT}-{RSYNC_PORT + 10} are all in use. "
                        f"Log syncing will be disabled.")
            self.rsync_port = None
            return

        if available_port != RSYNC_PORT:
            logger.info(f"Default rsync port {RSYNC_PORT} is in use, using alternative port {available_port}")

        log_dir = os.path.expanduser(self.config.worker.log_dir)
        os.makedirs(log_dir, exist_ok=True)

        # Create temporary rsync config file
        config_content = f"""# rsync daemon config for GPU scheduler log syncing
[scheduler-logs]
    path = {log_dir}
    comment = GPU Scheduler logs
    read only = no
    use chroot = no
"""
        # Create temp file that won't be deleted (we need it for daemon lifetime)
        fd, config_path = tempfile.mkstemp(prefix='rsyncd_', suffix='.conf', text=True)
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(config_content)
        except:
            os.close(fd)  # Close if write fails
            raise

        self.rsync_config_file = config_path

        # Start rsync daemon on available_port (no sudo needed for ports > 1024)
        try:
            self.rsync_daemon_process = subprocess.Popen(
                [
                    'rsync',
                    '--daemon',
                    '--no-detach',  # Run in foreground
                    f'--port={available_port}',
                    f'--config={config_path}',
                    '--log-file=/dev/null'  # Suppress rsync logs
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            self.rsync_port = available_port
            logger.info(f"rsync daemon started on port {available_port} for log syncing")
            
            # Store rsync PID in the lockfile for cleanup on crash/stale lock removal
            if self.singleton:
                try:
                    self.singleton.update_lockfile_data(rsync_pid=self.rsync_daemon_process.pid)
                    logger.debug(f"Stored rsync daemon PID {self.rsync_daemon_process.pid} in lockfile")
                except Exception as e:
                    logger.warning(f"Failed to store rsync PID in lockfile: {e}")
        except FileNotFoundError:
            logger.error("rsync command not found - log syncing will be disabled")
            os.remove(config_path)
            self.rsync_config_file = None
            self.rsync_port = None
            # Don't raise - allow orchestrator to continue without rsync
        except OSError as e:
            if "Address already in use" in str(e):
                logger.error(f"Cannot bind to port {available_port}: address already in use. "
                           f"Log syncing will be disabled.")
            else:
                logger.error(f"Failed to start rsync daemon: {e}. Log syncing will be disabled.")
            os.remove(config_path)
            self.rsync_config_file = None
            self.rsync_port = None
            # Don't raise - allow orchestrator to continue without rsync
        except Exception as e:
            logger.error(f"Failed to start rsync daemon: {e}. Log syncing will be disabled.")
            os.remove(config_path)
            self.rsync_config_file = None
            self.rsync_port = None
            # Don't raise - allow orchestrator to continue without rsync

    def _check_rsync_daemon(self):
        """Check if rsync daemon is still running and restart if needed."""
        if not self.rsync_daemon_process:
            # Rsync was never started or is disabled
            return

        # Check if process is still alive
        returncode = self.rsync_daemon_process.poll()
        if returncode is not None:
            # Process has died
            logger.error(f"Rsync daemon has died with return code {returncode}. Attempting to restart...")
            
            # Clean up old process state
            self.rsync_daemon_process = None
            
            # Try to restart
            try:
                self._start_rsync_daemon()
                if self.rsync_daemon_process:
                    logger.info(f"Successfully restarted rsync daemon on port {self.rsync_port}")
                else:
                    logger.error("Failed to restart rsync daemon - log syncing will be unavailable")
            except Exception as e:
                logger.error(f"Error restarting rsync daemon: {e}")

    def _stop_rsync_daemon(self):
        """Stop rsync daemon subprocess."""
        if self.rsync_daemon_process:
            try:
                logger.info("Stopping rsync daemon...")
                self.rsync_daemon_process.terminate()
                try:
                    self.rsync_daemon_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("rsync daemon did not stop gracefully, killing it")
                    self.rsync_daemon_process.kill()
                    self.rsync_daemon_process.wait()
                logger.info("rsync daemon stopped")
            except Exception as e:
                logger.error(f"Error stopping rsync daemon: {e}")

        # Clean up config file
        if self.rsync_config_file and os.path.exists(self.rsync_config_file):
            try:
                os.remove(self.rsync_config_file)
            except Exception as e:
                logger.warning(f"Failed to remove rsync config file: {e}")
