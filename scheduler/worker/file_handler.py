import os
import logging
import time

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

    def cleanup_old_logs(self, max_age_hours: int = 24) -> int:
        """
        Remove log files older than the specified age.

        Args:
            max_age_hours: Maximum age of logs to keep in hours (default: 24)

        Returns:
            Number of log files removed
        """
        if not os.path.exists(self.log_dir):
            return 0

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        removed_count = 0

        try:
            for filename in os.listdir(self.log_dir):
                if not filename.endswith('.log'):
                    continue

                file_path = os.path.join(self.log_dir, filename)

                # Skip if not a file
                if not os.path.isfile(file_path):
                    continue

                # Check file modification time
                try:
                    file_mtime = os.path.getmtime(file_path)
                    age_seconds = current_time - file_mtime

                    if age_seconds > max_age_seconds:
                        os.remove(file_path)
                        removed_count += 1
                        logger.info(f"Removed old log file: {filename} (age: {age_seconds / 3600:.1f} hours)")
                except OSError as e:
                    logger.warning(f"Failed to process log file {filename}: {e}")

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old log files (older than {max_age_hours} hours)")

        except Exception as e:
            logger.error(f"Error during log cleanup: {e}")

        return removed_count
