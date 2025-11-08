"""Log position tracking for incremental log streaming"""

import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from scheduler.core import Config
from scheduler.api.schemas import LogRequest, LogChunk

logger = logging.getLogger(__name__)


@dataclass
class LogPosition:
    """Track log position for a single job"""
    stdout_pos: int
    stderr_pos: int
    eof: bool
    consecutive_errors: int


class LogPositionManager:
    """Tracks expected log positions for all jobs and validates incoming chunks"""

    def __init__(self, config: Config, job_manager):
        """
        Initialize log position manager.

        Args:
            config: Configuration instance
            job_manager: JobManager instance to query jobs by node
        """
        self.config = config
        self.job_manager = job_manager
        # job_id → LogPosition
        self.positions: Dict[str, LogPosition] = {}
        self.max_consecutive_errors = 3

        logger.info("LogPositionManager initialized")

    def init_job(self, job_id: str):
        """Initialize tracking for new job"""
        self.positions[job_id] = LogPosition(
            stdout_pos=0,
            stderr_pos=0,
            eof=False,
            consecutive_errors=0
        )

    def get_requests_for_node(self, node_name: str) -> List[LogRequest]:
        """
        Get log requests for all jobs running on a node.

        Args:
            node_name: Worker node name

        Returns:
            List of LogRequest for jobs on this node
        """
        requests = []

        # Get all jobs assigned to this node
        jobs = self.job_manager.list_jobs()
        node_jobs = [job for job in jobs if job.assigned_node == node_name]

        for job in node_jobs:
            job_id = job.job_id

            # Initialize tracking if not already done
            if job_id not in self.positions:
                self.init_job(job_id)

            pos = self.positions[job_id]

            # Don't request if EOF received or too many errors
            if pos.eof:
                continue

            if pos.consecutive_errors >= self.max_consecutive_errors:
                logger.warning(
                    f"Job {job_id} exceeded max consecutive errors ({self.max_consecutive_errors}), "
                    "stopping log requests"
                )
                continue

            requests.append(LogRequest(
                job_id=job_id,
                stdout_pos=pos.stdout_pos,
                stderr_pos=pos.stderr_pos
            ))

        return requests

    def process_chunk(self, chunk: LogChunk) -> bool:
        """
        Process received log chunk from worker.

        Args:
            chunk: LogChunk received from worker

        Returns:
            True if chunk was valid and processed, False otherwise
        """
        job_id = chunk.job_id

        # Initialize if needed
        if job_id not in self.positions:
            self.init_job(job_id)

        pos = self.positions[job_id]

        # Check for position error from worker
        if chunk.position_error:
            pos.consecutive_errors += 1
            logger.warning(
                f"Worker reported position error for job {job_id}, "
                f"error count: {pos.consecutive_errors}/{self.max_consecutive_errors}"
            )
            return False

        # Validate position match
        stdout_match = chunk.requested_stdout_pos == pos.stdout_pos
        stderr_match = chunk.requested_stderr_pos == pos.stderr_pos

        if not (stdout_match and stderr_match):
            pos.consecutive_errors += 1
            logger.error(
                f"Position mismatch for job {job_id} (error {pos.consecutive_errors}/{self.max_consecutive_errors}): "
                f"expected stdout={pos.stdout_pos}, got {chunk.requested_stdout_pos}; "
                f"expected stderr={pos.stderr_pos}, got {chunk.requested_stderr_pos}"
            )
            return False

        # Success - reset error count
        pos.consecutive_errors = 0

        # Write chunks to disk
        self._write_chunk(chunk)

        # Update positions
        pos.stdout_pos = chunk.new_stdout_pos
        pos.stderr_pos = chunk.new_stderr_pos

        # Mark EOF if received
        if chunk.eof:
            pos.eof = True
            logger.info(f"Received EOF for job {job_id}, log streaming complete")

        return True

    def _write_chunk(self, chunk: LogChunk):
        """
        Append log chunk to files on head node.

        Args:
            chunk: LogChunk to write
        """
        log_dir = os.path.expanduser(self.config.worker.log_dir)
        os.makedirs(log_dir, exist_ok=True)

        # Write stdout chunk
        if chunk.stdout_chunk:
            stdout_path = os.path.join(log_dir, f"{chunk.job_id}.stdout.log")
            try:
                # Open in append mode
                with open(stdout_path, 'a') as f:
                    # Verify file position matches expected position
                    current_size = f.tell()
                    if current_size != chunk.requested_stdout_pos:
                        logger.warning(
                            f"Stdout file size mismatch for job {chunk.job_id}: "
                            f"expected {chunk.requested_stdout_pos}, got {current_size}. "
                            "Re-seeking to requested position."
                        )
                        # This shouldn't happen in normal operation, but handle it
                        f.seek(chunk.requested_stdout_pos)

                    f.write(chunk.stdout_chunk)
                    f.flush()
            except Exception as e:
                logger.error(f"Failed to write stdout chunk for job {chunk.job_id}: {e}")

        # Write stderr chunk
        if chunk.stderr_chunk:
            stderr_path = os.path.join(log_dir, f"{chunk.job_id}.stderr.log")
            try:
                with open(stderr_path, 'a') as f:
                    current_size = f.tell()
                    if current_size != chunk.requested_stderr_pos:
                        logger.warning(
                            f"Stderr file size mismatch for job {chunk.job_id}: "
                            f"expected {chunk.requested_stderr_pos}, got {current_size}. "
                            "Re-seeking to requested position."
                        )
                        f.seek(chunk.requested_stderr_pos)

                    f.write(chunk.stderr_chunk)
                    f.flush()
            except Exception as e:
                logger.error(f"Failed to write stderr chunk for job {chunk.job_id}: {e}")

    def cleanup_job(self, job_id: str):
        """
        Clean up tracking for a job (optional, for memory management).

        Args:
            job_id: Job ID to stop tracking
        """
        if job_id in self.positions:
            del self.positions[job_id]
