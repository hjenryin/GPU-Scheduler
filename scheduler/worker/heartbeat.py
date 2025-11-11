import logging
import threading
import time
from typing import Optional

from scheduler.core import Config, Job
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.api import SchedulerClient

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """Sends periodic heartbeat to head node"""

    def __init__(
        self,
        node_name: str,
        head_address: str,
        gpu_monitor: GPUMonitor,
        config: Config
    ):
        """
        Initialize heartbeat sender.

        Args:
            node_name: This node's name
            head_address: Head node address
            gpu_monitor: GPUMonitor instance
            config: Configuration instance
        """
        self.node_name = node_name
        self.head_address = head_address
        self.gpu_monitor = gpu_monitor
        self.config = config

        # Create scheduler client
        self.client = SchedulerClient(address=head_address, config=config)

        # Get heartbeat configuration
        self.heartbeat_interval = config.worker.heartbeat_interval

        # Thread control
        self.running = False
        self.heartbeat_thread: Optional[threading.Thread] = None

        # Callback for cleanup notifications (gets active job IDs to keep)
        self.cleanup_callback = None

        logger.info(f"HeartbeatSender initialized for node {node_name} -> {head_address}")

    def start(self):
        """
        Start heartbeat thread.
        """
        if self.running:
            logger.warning("Heartbeat sender is already running")
            return

        self.running = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        logger.info("Heartbeat sender started")

    def stop(self):
        """
        Stop heartbeat thread.
        """
        if not self.running:
            logger.warning("Heartbeat sender is not running")
            return

        self.running = False
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)

        logger.info("Heartbeat sender stopped")

    def send_heartbeat(self) -> bool:
        """
        Send a single heartbeat to head node.

        Returns:
            True if shutdown requested by head, False otherwise
        """
        try:
            # Get latest GPU stats
            gpu_stats = self.gpu_monitor.get_latest_stats()

            # Send heartbeat and receive response
            response = self.client.send_heartbeat(self.node_name, gpu_stats)

            # Handle cleanup - tell worker which jobs to keep and which to run
            if self.cleanup_callback:
                recorded_job_ids = getattr(response, 'recorded_job_ids', [])
                running_job_ids = getattr(response, 'running_job_ids', [])

                # If response still uses old active_job_ids field, use it for backward compatibility
                if not recorded_job_ids and hasattr(response, 'active_job_ids'):
                    recorded_job_ids = response.active_job_ids

                self.cleanup_callback(recorded_job_ids, running_job_ids)

            if response.shutdown_requested:
                logger.info(f"Shutdown requested by head node for {self.node_name}")
                return True

            logger.debug(f"Sent heartbeat for node {self.node_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def poll_for_job(self) -> Optional[Job]:
        """
        Long-poll head node for job assignment.

        Returns:
            Job if assigned, None if no job available
        """
        try:
            job = self.client.poll_for_job(self.node_name, timeout=self.config.worker.job_poll_timeout)
            if job:
                logger.info(f"Received job assignment: {job.job_id}")
            return job
        except Exception as e:
            logger.error(f"Failed to poll for job: {e}")
            return None

    def _heartbeat_loop(self):
        """Internal heartbeat loop thread."""
        logger.info("Heartbeat loop started")

        while self.running:
            shutdown_requested = self.send_heartbeat()
            if shutdown_requested:
                logger.info("Shutdown requested - stopping heartbeat loop")
                self.running = False
                break
            time.sleep(self.heartbeat_interval)

        logger.info("Heartbeat loop stopped")

    def set_cleanup_callback(self, callback):
        """
        Set the callback function to be called for job cleanup.

        Args:
            callback: Function that takes (recorded_job_ids, running_job_ids).
                     recorded_job_ids: All job IDs to keep log files for
                     running_job_ids: Job IDs that should be actively running (terminate others)
        """
        self.cleanup_callback = callback

    def set_purge_callback(self, callback):
        """
        Deprecated: Use set_cleanup_callback instead.
        Maintained for backward compatibility.
        """
        self.set_cleanup_callback(callback)

    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            True if shutdown was requested by the head node
        """
        return not self.running
