import logging
import signal
import time
import threading
from datetime import datetime
from typing import Optional

from scheduler.core import Config, PermissionDeniedException
from scheduler.storage import FileBackend, SQLiteBackend
from scheduler.head.persistence import PersistenceManager
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.head.scheduler import Scheduler
from scheduler.head.api_server import APIServer

logger = logging.getLogger(__name__)

# Global orchestrator instance for API access
_orchestrator_instance: Optional['Orchestrator'] = None


class Orchestrator:
    """Main head node orchestrator"""

    def __init__(self, config: Config, singleton=None):
        """
        Initialize orchestrator.

        Args:
            config: Configuration instance
            singleton: SingletonDaemon instance for lock management
        """
        global _orchestrator_instance
        _orchestrator_instance = self
        
        self.config = config
        self.singleton = singleton
        self.running = False
        self._cluster_shutdown_requested = False
        self._cluster_shutdown_timeout = 60
        self._cluster_shutdown_force = False
        self.scheduler_thread: Optional[threading.Thread] = None

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
            
            # Send shutdown signals to all worker nodes
            # Note: In a real implementation, we would send HTTP requests to each worker
            # For now, we'll rely on the fact that stopping the head node will cause
            # workers to lose connection and stop themselves
            
            # Stop the head node itself
            logger.info("Stopping head node...")
            self.stop(graceful=True)
            
            logger.info("Cluster shutdown completed")
            
        except Exception as e:
            logger.error(f"Error during cluster shutdown: {e}", exc_info=True)
