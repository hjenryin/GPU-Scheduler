import logging
import threading
import time
from typing import Optional

from scheduler.core.config import Config
from scheduler.core.models import Job
from scheduler.core import constants
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.api.client import SchedulerClient

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
        worker_config = config.get('worker', {})
        self.heartbeat_interval = worker_config.get('heartbeat_interval', constants.DEFAULT_HEARTBEAT_INTERVAL)

        # Thread control
        self.running = False
        self.heartbeat_thread: Optional[threading.Thread] = None

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
            True if successful, False otherwise
        """
        try:
            # Get latest GPU stats
            gpu_stats = self.gpu_monitor.get_latest_stats()

            # Send heartbeat
            self.client.send_heartbeat(self.node_name, gpu_stats)
            logger.debug(f"Sent heartbeat for node {self.node_name}")
            return True
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
            job = self.client.poll_for_job(self.node_name, timeout=30)
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
            self.send_heartbeat()
            time.sleep(self.heartbeat_interval)

        logger.info("Heartbeat loop stopped")
