import logging
import signal
import time
import threading
from typing import Optional

from scheduler.core import Config, PermissionDeniedException
from scheduler.storage import FileBackend, SQLiteBackend
from scheduler.head.persistence import PersistenceManager
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.head.scheduler import Scheduler
from scheduler.head.api_server import APIServer

logger = logging.getLogger(__name__)


class Orchestrator:
    """Main head node orchestrator"""

    def __init__(self, config: Config):
        """
        Initialize orchestrator.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.running = False
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
            timeout = 60  # 60 seconds timeout
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
        free_gpus = sum(len(node.get_free_gpus()) for node in nodes)
        used_gpus = total_gpus - free_gpus

        return {
            'running': self.running,
            'nodes': {
                'total': len(nodes),
                'connected': len([n for n in nodes if not n.is_timed_out(self.scheduler.heartbeat_timeout)])
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

    def _scheduler_loop(self):
        """Internal scheduler loop thread."""
        logger.info("Scheduler loop started")

        while self.running:
            try:
                # Run scheduler cycle
                self.scheduler.schedule_cycle()

                # Check for node timeouts
                self.node_manager.check_timeouts()

                # Sleep for schedule interval
                time.sleep(self.config.head.scheduling_interval)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(1)  # Brief pause before retrying

        logger.info("Scheduler loop stopped")

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop(graceful=True)
