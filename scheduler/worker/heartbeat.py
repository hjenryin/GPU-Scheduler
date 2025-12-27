import logging
import threading
import time
from typing import Optional, List

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

            # Send heartbeat with long-poll timeout
            response = self.client.send_heartbeat(
                self.node_name,
                gpu_stats,
                shutdown_acknowledged=False,
                timeout=self.heartbeat_interval
            )

            if response.shutdown_requested:
                logger.info(f"Shutdown requested by head node for {self.node_name}")

                # Send immediate confirmation heartbeat
                try:
                    logger.info("Sending immediate shutdown confirmation")
                    self.client.send_heartbeat(
                        self.node_name,
                        gpu_stats,
                        shutdown_acknowledged=True
                    )
                    logger.info("Shutdown confirmation sent")
                except Exception as e:
                    logger.error(f"Failed to send confirmation: {e}")

                return True

            logger.debug(f"Sent heartbeat for node {self.node_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to send heartbeat: {e}")
            return False

    def _heartbeat_loop(self):
        """Internal heartbeat loop thread."""
        logger.info("Heartbeat loop started")

        while self.running:
            shutdown_requested = self.send_heartbeat()
            if shutdown_requested:
                logger.info("Shutdown requested - stopping heartbeat loop")
                self.running = False
                break
            # NO sleep! send_heartbeat() already waited via long-polling

        logger.info("Heartbeat loop stopped")

    def is_shutdown_requested(self) -> bool:
        """
        Check if shutdown has been requested.
        
        Returns:
            True if shutdown was requested by the head node
        """
        return not self.running
