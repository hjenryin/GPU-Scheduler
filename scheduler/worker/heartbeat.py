import logging
import threading
import time
from typing import Optional, List

from scheduler.core import Config, Job
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.api import SchedulerClient
from scheduler.api.schemas import LogRequest

logger = logging.getLogger(__name__)


class HeartbeatSender:
    """Sends periodic heartbeat to head node"""

    def __init__(
        self,
        node_name: str,
        head_address: str,
        gpu_monitor: GPUMonitor,
        config: Config,
        log_reader=None  # LogChunkReader instance (optional, set later to avoid circular dependency)
    ):
        """
        Initialize heartbeat sender.

        Args:
            node_name: This node's name
            head_address: Head node address
            gpu_monitor: GPUMonitor instance
            config: Configuration instance
            log_reader: LogChunkReader instance (optional)
        """
        self.node_name = node_name
        self.head_address = head_address
        self.gpu_monitor = gpu_monitor
        self.config = config
        self.log_reader = log_reader

        # Create scheduler client
        self.client = SchedulerClient(address=head_address, config=config)

        # Get heartbeat configuration
        self.heartbeat_interval = config.worker.heartbeat_interval

        # Thread control
        self.running = False
        self.heartbeat_thread: Optional[threading.Thread] = None

        # Store pending log requests from head
        self.pending_log_requests: List[LogRequest] = []

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
        Send a single heartbeat to head node with log chunks.

        Returns:
            True if shutdown requested by head, False otherwise
        """
        try:
            # Get latest GPU stats
            gpu_stats = self.gpu_monitor.get_latest_stats()

            # Read log chunks for pending requests (if log_reader is available)
            log_chunks = []
            if self.log_reader:
                log_chunks = self.log_reader.read_chunks(self.pending_log_requests)

            # Send heartbeat and receive response
            response = self.client.send_heartbeat(self.node_name, gpu_stats, log_chunks)

            # Store log requests from response for next heartbeat
            self.pending_log_requests = response.log_requests

            # Handle cleanup - tell worker which jobs to keep (purge all others)
            if hasattr(response, 'active_job_ids') and self.cleanup_callback:
                self.cleanup_callback(response.active_job_ids)
            # Fallback for backward compatibility with old purge_job_ids
            elif hasattr(response, 'purge_job_ids') and response.purge_job_ids and self.cleanup_callback:
                # Old style - just purge specific jobs
                for job_id in response.purge_job_ids:
                    logger.info(f"Received purge request for job {job_id}")
                    self.cleanup_callback([])  # Empty keep list means purge the ones specified

            if response.shutdown_requested:
                logger.info(f"Shutdown requested by head node for {self.node_name}")
                return True

            logger.debug(
                f"Sent heartbeat for node {self.node_name} "
                f"(sent {len(log_chunks)} log chunks, received {len(self.pending_log_requests)} log requests)"
            )
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
            logger.info(f"[TRACE] Polling for job on node {self.node_name}")
            job = self.client.poll_for_job(self.node_name, timeout=30)
            if job:
                logger.info(f"[TRACE] Received job assignment: {job.job_id}")
            else:
                logger.info("[TRACE] No job received")
            return job
        except Exception as e:
            logger.error(f"[TRACE] Failed to poll for job: {e}")
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
            callback: Function that takes a list of active job IDs to keep.
                     Worker should clean up any jobs not in this list.
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
