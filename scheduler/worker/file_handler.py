import os
import logging

from scheduler.core import Config, ensure_dir_exists

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles file operations for job execution"""

    def __init__(self, config: Config):
        """
        Initialize file handler.

        Args:
            config: Configuration instance
        """
        self.config = config

        # Get worker configuration
        self.work_dir = os.path.expanduser(config.worker.work_dir)
        self.log_dir = os.path.expanduser(config.worker.log_dir)

        # Ensure directories exist
        ensure_dir_exists(self.work_dir)
        ensure_dir_exists(self.log_dir)

        logger.info(f"FileHandler initialized with work_dir={self.work_dir}, log_dir={self.log_dir}")

    def get_job_log_path(self, job_id: str, stderr: bool = False) -> str:
        """
        Get path to job log file.

        Args:
            job_id: Job ID
            stderr: If True, return stderr log path

        Returns:
            Path to log file
        """
        suffix = 'stderr' if stderr else 'stdout'
        log_filename = f"{job_id}.{suffix}.log"
        return os.path.join(self.log_dir, log_filename)

    def get_job_snapshot_dir(self, job_id: str) -> str:
        """
        Get directory path for job snapshot restoration.
        
        Creates a worktree directory at ~/.scheduler/work/job-{job_id}/snapshot/
        as specified in GIT_DEV_PLAN.md

        Args:
            job_id: Job ID

        Returns:
            Path to snapshot directory
        """
        snapshot_dir = os.path.join(self.work_dir, job_id, "snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)
        return snapshot_dir
