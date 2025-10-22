import os
import shutil
import logging
import time
from datetime import datetime

from scheduler.core.config import Config
from scheduler.core.exceptions import PermissionDeniedException
from scheduler.core import constants
from scheduler.core.utils import ensure_dir_exists, generate_versioned_filename

logger = logging.getLogger(__name__)


class FileHandler:
    """Handles script versioning and file operations"""

    def __init__(self, config: Config):
        """
        Initialize file handler.

        Args:
            config: Configuration instance
        """
        self.config = config

        # Get worker configuration
        worker_config = config.get('worker', {})
        self.work_dir = worker_config.get('work_dir', constants.DEFAULT_WORKER_DIR)
        self.log_dir = worker_config.get('log_dir', os.path.join(self.work_dir, 'logs'))

        # Ensure directories exist
        ensure_dir_exists(self.work_dir)
        ensure_dir_exists(self.log_dir)

        logger.info(f"FileHandler initialized with work_dir={self.work_dir}, log_dir={self.log_dir}")

    def create_versioned_copy(self, script_path: str, job_id: str) -> str:
        """
        Create a versioned copy of a script.

        Args:
            script_path: Original script path
            job_id: Job ID

        Returns:
            Path to versioned copy

        Raises:
            FileNotFoundError: If script doesn't exist
            PermissionDeniedException: If cannot create copy
        """
        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Script not found: {script_path}")

        try:
            # Get original filename
            original_name = os.path.basename(script_path)

            # Generate versioned filename
            versioned_name = generate_versioned_filename(original_name, job_id)

            # Create destination path in work directory
            dest_path = os.path.join(self.work_dir, versioned_name)

            # Copy the file
            shutil.copy2(script_path, dest_path)

            # Make it executable
            try:
                os.chmod(dest_path, 0o755)
            except:
                pass  # Best effort

            logger.info(f"Created versioned copy: {script_path} -> {dest_path}")
            return dest_path
        except PermissionError as e:
            raise PermissionDeniedException(f"Cannot create versioned copy: {e}")
        except Exception as e:
            logger.error(f"Failed to create versioned copy: {e}")
            raise

    def cleanup_versioned_files(self, max_age_hours: int = 24):
        """
        Clean up old versioned files.

        Args:
            max_age_hours: Maximum age of files to keep
        """
        try:
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            deleted_count = 0

            # Clean up work directory
            for filename in os.listdir(self.work_dir):
                filepath = os.path.join(self.work_dir, filename)

                # Skip directories
                if not os.path.isfile(filepath):
                    continue

                # Check if file is old enough
                file_age = current_time - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        deleted_count += 1
                        logger.debug(f"Deleted old file: {filepath}")
                    except Exception as e:
                        logger.warning(f"Failed to delete {filepath}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} old versioned files")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

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
