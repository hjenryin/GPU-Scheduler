"""Log syncer using rsync algorithm over HTTP"""

import os
import time
import logging
import threading
from typing import List, Dict, Any
import pyrsync2

from scheduler.core import Config
from scheduler.api import SchedulerClient

logger = logging.getLogger(__name__)


class LogSyncer:
    """Syncs worker logs to head node using rsync algorithm over HTTP"""

    def __init__(self, config: Config, client: SchedulerClient, node_name: str):
        """
        Initialize log syncer.

        Args:
            config: Configuration instance
            client: SchedulerClient for HTTP communication
            node_name: This worker's node name
        """
        self.config = config
        self.client = client
        self.node_name = node_name
        self.log_dir = os.path.expanduser(config.worker.log_dir)
        self.sync_interval = 10  # Sync every 10 seconds
        self.running = False
        self.sync_thread = None

        logger.info(f"LogSyncer initialized for node {node_name}")

    def start(self):
        """Start periodic log syncing"""
        if self.running:
            logger.warning("LogSyncer already running")
            return

        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        logger.info("LogSyncer started")

    def stop(self):
        """Stop log syncing"""
        if not self.running:
            return

        self.running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=5)
        logger.info("LogSyncer stopped")

    def _sync_loop(self):
        """Main sync loop"""
        while self.running:
            try:
                self.sync_all_logs()
            except Exception as e:
                logger.error(f"Log sync failed: {e}", exc_info=True)
            time.sleep(self.sync_interval)

    def sync_all_logs(self):
        """Sync all log files for jobs on this worker"""
        if not os.path.exists(self.log_dir):
            return

        # Find all log files
        log_files = [
            f for f in os.listdir(self.log_dir)
            if f.endswith('.log') and not f.endswith('.offset')
        ]

        if not log_files:
            return

        synced_count = 0
        total_bytes = 0

        for log_file in log_files:
            try:
                bytes_sent = self.sync_file(log_file)
                if bytes_sent > 0:
                    synced_count += 1
                    total_bytes += bytes_sent
            except Exception as e:
                logger.error(f"Failed to sync {log_file}: {e}")

        if synced_count > 0:
            logger.info(
                f"Synced {synced_count}/{len(log_files)} log files "
                f"({total_bytes} bytes transferred)"
            )

    def sync_file(self, filename: str) -> int:
        """
        Sync a single log file using rsync delta algorithm.

        Args:
            filename: Log filename (e.g., "job-123.stdout.log")

        Returns:
            Number of bytes in delta sent
        """
        file_path = os.path.join(self.log_dir, filename)

        # Check if file exists and has content
        if not os.path.exists(file_path):
            return 0

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            return 0

        # Step 1: Get checksums from head node
        checksums = self.client.get_log_checksums(self.node_name, filename)

        # Step 2: Generate delta
        with open(file_path, 'rb') as f:
            delta = list(pyrsync2.rsyncdelta(f, checksums))

        # If delta is empty, file is already synced
        if not delta:
            return 0

        # Step 3: Send delta to head
        delta_bytes = self._estimate_delta_size(delta)
        self.client.apply_log_delta(self.node_name, filename, delta)

        logger.debug(f"Synced {filename}: {delta_bytes} bytes delta")
        return delta_bytes

    def _estimate_delta_size(self, delta: List) -> int:
        """Estimate size of delta data"""
        total = 0
        for item in delta:
            if isinstance(item, bytes):
                total += len(item)
        return total
