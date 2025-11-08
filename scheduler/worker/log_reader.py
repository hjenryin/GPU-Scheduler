"""Log chunk reader for workers to stream logs to head node"""

import os
import logging
from typing import List, Optional, Set
from dataclasses import dataclass

from scheduler.core import Config
from scheduler.api.schemas import LogRequest, LogChunk
from scheduler.worker.file_handler import FileHandler

logger = logging.getLogger(__name__)


@dataclass
class ReadResult:
    """Result of reading from a log file"""
    chunk: str
    new_pos: int
    at_eof: bool
    error: bool


class LogChunkReader:
    """Reads log chunks from specific file positions"""

    def __init__(self, config: Config, file_handler: FileHandler):
        """
        Initialize log chunk reader.

        Args:
            config: Configuration instance
            file_handler: FileHandler for accessing log files
        """
        self.config = config
        self.file_handler = file_handler
        self.max_chunk_size = 50 * 1024  # 50KB per stream per heartbeat (100KB total)

        # Track which jobs have finished (but may still have logs to send)
        self.finished_jobs: Set[str] = set()

        logger.info("LogChunkReader initialized")

    def mark_job_finished(self, job_id: str):
        """
        Mark a job as finished (will send EOF when all logs sent).

        Args:
            job_id: Job ID that has finished
        """
        self.finished_jobs.add(job_id)
        logger.debug(f"Marked job {job_id} as finished, will send EOF when logs complete")

    def read_chunks(self, requests: List[LogRequest]) -> List[LogChunk]:
        """
        Read log chunks for all requested positions.

        Args:
            requests: List of log requests from head node

        Returns:
            List of log chunks to send back
        """
        chunks = []

        if requests:
            logger.info(f"Reading log chunks for {len(requests)} requests: {[(r.job_id, r.stdout_pos, r.stderr_pos) for r in requests]}")

        for req in requests:
            try:
                chunk = self._read_chunk_for_job(req)
                if chunk:
                    chunks.append(chunk)
                    stdout_bytes = len(chunk.stdout_chunk) if chunk.stdout_chunk else 0
                    stderr_bytes = len(chunk.stderr_chunk) if chunk.stderr_chunk else 0
                    logger.info(f"Read chunk for job {req.job_id}: stdout={stdout_bytes}B, stderr={stderr_bytes}B, eof={chunk.eof}")
            except Exception as e:
                logger.error(f"Error reading log chunk for job {req.job_id}: {e}")
                # Send error chunk
                chunks.append(LogChunk(
                    job_id=req.job_id,
                    stdout_chunk="",
                    requested_stdout_pos=req.stdout_pos,
                    new_stdout_pos=req.stdout_pos,
                    stderr_chunk="",
                    requested_stderr_pos=req.stderr_pos,
                    new_stderr_pos=req.stderr_pos,
                    eof=False,
                    position_error=True
                ))

        return chunks

    def _read_chunk_for_job(self, req: LogRequest) -> Optional[LogChunk]:
        """
        Read log chunk for a single job.

        Args:
            req: Log request with positions to read from

        Returns:
            LogChunk or None if no data
        """
        job_id = req.job_id

        # Get log file paths
        stdout_path = self.file_handler.get_job_log_path(job_id, stderr=False)
        stderr_path = self.file_handler.get_job_log_path(job_id, stderr=True)

        # Read stdout chunk
        stdout_result = self._read_from_position(stdout_path, req.stdout_pos)

        # Read stderr chunk
        stderr_result = self._read_from_position(stderr_path, req.stderr_pos)

        # Check if both streams reached EOF
        both_at_eof = stdout_result.at_eof and stderr_result.at_eof

        # Determine if we should send EOF:
        # - Job must be marked as finished
        # - AND both streams must be at EOF (all logs sent)
        job_finished = job_id in self.finished_jobs
        send_eof = job_finished and both_at_eof

        if send_eof:
            logger.info(
                f"Sending EOF for job {job_id} (job finished and all logs sent: "
                f"stdout_eof={stdout_result.at_eof}, stderr_eof={stderr_result.at_eof})"
            )
            # Clean up tracking
            self.finished_jobs.discard(job_id)

        # Return chunk
        return LogChunk(
            job_id=job_id,
            stdout_chunk=stdout_result.chunk,
            requested_stdout_pos=req.stdout_pos,
            new_stdout_pos=stdout_result.new_pos,
            stderr_chunk=stderr_result.chunk,
            requested_stderr_pos=req.stderr_pos,
            new_stderr_pos=stderr_result.new_pos,
            eof=send_eof,
            position_error=stdout_result.error or stderr_result.error
        )

    def _read_from_position(self, file_path: str, position: int) -> ReadResult:
        """
        Read chunk from file starting at position.

        Args:
            file_path: Path to log file
            position: Byte position to start reading from

        Returns:
            ReadResult with chunk data and metadata
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                # File doesn't exist yet (job may not have started logging)
                return ReadResult(chunk="", new_pos=position, at_eof=True, error=False)

            with open(file_path, 'r') as f:
                # Get file size
                f.seek(0, os.SEEK_END)
                file_size = f.tell()

                # Check if requested position is beyond file size
                if position > file_size:
                    logger.warning(
                        f"Requested position {position} beyond file size {file_size} for {file_path}"
                    )
                    # This is an error - position should never be ahead of file
                    return ReadResult(chunk="", new_pos=position, at_eof=False, error=True)

                # Seek to requested position
                f.seek(position)

                # Read up to max_chunk_size
                chunk = f.read(self.max_chunk_size)

                # Calculate new position
                new_pos = position + len(chunk)

                # Check if we're at EOF
                at_eof = (new_pos >= file_size)

                return ReadResult(
                    chunk=chunk,
                    new_pos=new_pos,
                    at_eof=at_eof,
                    error=False
                )

        except Exception as e:
            logger.error(f"Error reading log file {file_path} at position {position}: {e}")
            return ReadResult(chunk="", new_pos=position, at_eof=False, error=True)
