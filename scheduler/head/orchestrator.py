import logging
import signal
import time
import threading
import subprocess
import tempfile
import os
from datetime import datetime
from typing import Optional

from scheduler.core import Config, PermissionDeniedException
from scheduler.storage import FileBackend, SQLiteBackend
from scheduler.manager import PersistenceManager, JobManager, NodeManager, Scheduler
from scheduler.head.api_server import APIServer

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
        self._cluster_shutdown_requested = False
        self._cluster_shutdown_timeout = 60
        self._cluster_shutdown_force = False
        self.scheduler_thread: Optional[threading.Thread] = None

        # rsync daemon for log syncing
        self.rsync_daemon_process: Optional[subprocess.Popen] = None
        self.rsync_config_file: Optional[str] = None

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

    def stop(self, graceful: bool = True):
        """
        Stop the orchestrator and all components.

        Args:
            graceful: If True, wait for jobs to complete
        """
        if not self.running:
            logger.warning("Orchestrator is not running")
            return

        logger.info("Stopping orchestrator...")

        # Signal scheduler to stop
        self.running = False

        if graceful:
            # Wait for running jobs to complete (with timeout)
            logger.info("Waiting for running jobs to complete...")
            timeout = self.config.head.graceful_shutdown_timeout
            start_time = time.time()

            while time.time() - start_time < timeout:
                running_jobs = self.job_manager.get_running_jobs()
                if not running_jobs:
                    break
                time.sleep(1)

            if running_jobs:
                logger.warning(f"{len(running_jobs)} jobs still running after graceful shutdown timeout")

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

    def run(self):
        """
        Run the orchestrator main loop (blocking).
        """
        self.start()

        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            self.stop(graceful=True)
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
        if self.running:
            self.stop(graceful=True)
        # Re-raise KeyboardInterrupt to allow proper cleanup in parent contexts
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()

    def request_cluster_shutdown(self, graceful_timeout: int = 60, force: bool = False):
        """
        Request cluster-wide shutdown.
        
        Args:
            graceful_timeout: Seconds to wait for graceful shutdown
            force: Whether to force kill if graceful shutdown fails
        """
        logger.info(f"Cluster shutdown requested: timeout={graceful_timeout}, force={force}")
        self._cluster_shutdown_requested = True
        self._cluster_shutdown_timeout = graceful_timeout
        self._cluster_shutdown_force = force
        
        # Start cluster shutdown in a separate thread to avoid blocking API response
        shutdown_thread = threading.Thread(target=self._shutdown_cluster_worker, daemon=True)
        shutdown_thread.start()

    def _shutdown_cluster_worker(self):
        """Worker thread to handle cluster shutdown."""
        try:
            logger.info("Starting cluster shutdown process...")
            
            # Get all connected nodes
            nodes = self.node_manager.get_connected_nodes()
            logger.info(f"Shutting down {len(nodes)} connected nodes")
            
            # Request shutdown for all worker nodes
            # Workers will see this flag in their next heartbeat and shutdown gracefully
            self.node_manager.request_shutdown_all_workers()
            logger.info("Shutdown signal sent to all worker nodes via heartbeat mechanism")
            
            # Give workers time to receive the shutdown signal and stop
            # Workers send heartbeats every 5-10 seconds, so we need to wait at least that long
            # Add extra time for graceful shutdown (completing current jobs, cleanup, etc.)
            shutdown_timeout = 15  # 15 seconds should be enough for one heartbeat cycle + cleanup
            logger.info(f"Waiting {shutdown_timeout} seconds for workers to shut down...")
            time.sleep(shutdown_timeout)
            
            # Stop the head node itself
            logger.info("Stopping head node...")
            self.stop(graceful=True)
            
            logger.info("Cluster shutdown completed")

        except Exception as e:
            logger.error(f"Error during cluster shutdown: {e}", exc_info=True)

    def _start_rsync_daemon(self):
        """Start rsync daemon as subprocess for log syncing (no sudo required)."""
        log_dir = os.path.expanduser(self.config.worker.log_dir)
        os.makedirs(log_dir, exist_ok=True)

        # Create temporary rsync config file
        config_content = f"""# rsync daemon config for GPU scheduler log syncing
[scheduler-logs]
    path = {log_dir}
    comment = GPU Scheduler logs
    read only = no
    use chroot = no
    uid = {os.getuid()}
    gid = {os.getgid()}
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

        # Start rsync daemon on port 8873 (no sudo needed for ports > 1024)
        try:
            self.rsync_daemon_process = subprocess.Popen(
                [
                    'rsync',
                    '--daemon',
                    '--no-detach',  # Run in foreground
                    '--port=8873',   # Custom port (no sudo required)
                    f'--config={config_path}',
                    '--log-file=/dev/null'  # Suppress rsync logs
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            logger.info("rsync daemon started on port 8873 for log syncing")
        except FileNotFoundError:
            logger.error("rsync command not found - log syncing will not work")
            os.remove(config_path)
            self.rsync_config_file = None
            raise
        except Exception as e:
            logger.error(f"Failed to start rsync daemon: {e}")
            os.remove(config_path)
            self.rsync_config_file = None
            raise

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
