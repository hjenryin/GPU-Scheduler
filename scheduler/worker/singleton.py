import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SingletonDaemon:
    """Ensures only one daemon runs per machine"""

    def __init__(self, lockfile_path: str):
        """
        Initialize singleton daemon.

        Args:
            lockfile_path: Path to lock file
        """
        self.lockfile_path = lockfile_path
        self.lockfile: Optional[int] = None  # File descriptor

    def acquire_lock(self) -> bool:
        """
        Try to acquire singleton lock.

        Returns:
            True if lock acquired, False if another daemon is running
        """
        try:
            # Create lock file directory if needed
            lockdir = os.path.dirname(self.lockfile_path)
            if lockdir and not os.path.exists(lockdir):
                os.makedirs(lockdir, exist_ok=True)

            # Try to open and lock the file
            # Use exclusive creation flag - fails if file exists
            try:
                self.lockfile = os.open(self.lockfile_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                # Write PID to lockfile
                os.write(self.lockfile, str(os.getpid()).encode())
                logger.info(f"Acquired singleton lock: {self.lockfile_path}")
                return True
            except FileExistsError:
                # Lock file exists - check if process is still running
                if os.path.exists(self.lockfile_path):
                    try:
                        with open(self.lockfile_path, 'r') as f:
                            pid = int(f.read().strip())

                        # Check if process is still running
                        try:
                            os.kill(pid, 0)  # Doesn't actually kill, just checks if process exists
                            logger.warning(f"Another daemon is running (PID: {pid})")
                            return False
                        except OSError:
                            # Process not running, stale lock file
                            logger.info(f"Removing stale lock file (PID {pid} not running)")
                            os.remove(self.lockfile_path)
                            # Try again
                            return self.acquire_lock()
                    except (ValueError, FileNotFoundError):
                        # Invalid or missing lock file, remove and try again
                        try:
                            os.remove(self.lockfile_path)
                        except:
                            pass
                        return self.acquire_lock()
                return False
        except Exception as e:
            logger.error(f"Failed to acquire lock: {e}")
            return False

    def release_lock(self):
        """
        Release singleton lock.
        """
        if self.lockfile is not None:
            try:
                os.close(self.lockfile)
                self.lockfile = None
            except:
                pass

        if os.path.exists(self.lockfile_path):
            try:
                os.remove(self.lockfile_path)
                logger.info(f"Released singleton lock: {self.lockfile_path}")
            except Exception as e:
                logger.warning(f"Failed to remove lock file: {e}")

    def __enter__(self):
        """Context manager entry."""
        if not self.acquire_lock():
            raise RuntimeError("Failed to acquire singleton lock - another daemon is running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release_lock()


def is_daemon_running(lockfile_path: str) -> bool:
    """
    Check if daemon is already running.

    Args:
        lockfile_path: Path to lock file

    Returns:
        True if daemon is running
    """
    if not os.path.exists(lockfile_path):
        return False

    try:
        with open(lockfile_path, 'r') as f:
            pid = int(f.read().strip())

        # Check if process is still running
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # Process not running
            return False
    except (ValueError, FileNotFoundError):
        return False
