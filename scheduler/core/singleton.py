import os
import logging
import signal
import time
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def _cleanup_rsync_daemon(rsync_pid: int) -> None:
    """
    Kill an rsync daemon process if it's actually an rsync daemon.
    
    Args:
        rsync_pid: Process ID to check and potentially kill
    """
    try:
        # Verify it's actually an rsync process before killing
        result = subprocess.run(
            ['ps', '-p', str(rsync_pid), '-o', 'comm='],
            capture_output=True,
            text=True,
            timeout=2
        )
        
        if result.returncode == 0 and 'rsync' in result.stdout.lower():
            logger.info(f"Killing orphaned rsync daemon (PID {rsync_pid})")
            try:
                os.kill(rsync_pid, signal.SIGTERM)
                # Wait for graceful termination with multiple checks
                for _ in range(10):  # Check up to 1 second (10 * 0.1s)
                    time.sleep(0.1)
                    try:
                        os.kill(rsync_pid, 0)
                    except OSError:
                        # Process is dead
                        return
                
                # Still alive after 1 second, force kill
                logger.warning(f"rsync daemon {rsync_pid} didn't respond to SIGTERM, using SIGKILL")
                os.kill(rsync_pid, signal.SIGKILL)
                # Wait for SIGKILL to take effect
                for _ in range(5):  # Check up to 0.5 seconds
                    time.sleep(0.1)
                    try:
                        os.kill(rsync_pid, 0)
                    except OSError:
                        # Process is finally dead
                        return
            except ProcessLookupError:
                pass  # Already dead
        else:
            logger.debug(f"PID {rsync_pid} is not an rsync process, skipping cleanup")
    except Exception as e:
        logger.warning(f"Failed to cleanup rsync daemon {rsync_pid}: {e}")


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
        self._original_signal_handlers = {}
        
        # Setup signal handlers for cleanup (only works in main thread)
        import threading
        if threading.current_thread() is threading.main_thread():
            self._setup_signal_handlers()
        else:
            logger.debug("Skipping signal handler setup (not in main thread)")

    def acquire_lock(self) -> bool:
        """
        Try to acquire singleton lock.

        Returns:
            True if lock acquired, False if another daemon is running
        """
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Create lock file directory if needed
                lockdir = os.path.dirname(self.lockfile_path)
                if lockdir and not os.path.exists(lockdir):
                    os.makedirs(lockdir, exist_ok=True)

                # Try to open and lock the file
                # Use exclusive creation flag - fails if file exists
                try:
                    import json
                    self.lockfile = os.open(self.lockfile_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    # Write PID to lockfile in JSON format
                    # rsync_pid will be added later by orchestrator if applicable
                    data = {"pid": os.getpid()}
                    os.write(self.lockfile, json.dumps(data).encode())
                    logger.info(f"Acquired singleton lock: {self.lockfile_path}")
                    return True
                except FileExistsError:
                    # Lock file exists - check if process is still running
                    if os.path.exists(self.lockfile_path):
                        try:
                            import json
                            with open(self.lockfile_path, 'r') as f:
                                data = json.load(f)
                            
                            pid = data.get('pid')
                            if not pid:
                                # Invalid lock file
                                os.remove(self.lockfile_path)
                                retry_count += 1
                                continue

                            # Check if process is still running
                            try:
                                os.kill(pid, 0)  # Doesn't actually kill, just checks if process exists
                                logger.warning(f"Another daemon is running (PID: {pid})")
                                return False
                            except OSError:
                                # Process not running, stale lock file
                                logger.info(f"Removing stale lock file (PID {pid} not running)")
                                
                                # Check if there's an rsync_pid and kill it too
                                rsync_pid = data.get('rsync_pid')
                                if rsync_pid:
                                    _cleanup_rsync_daemon(rsync_pid)
                                
                                os.remove(self.lockfile_path)
                                retry_count += 1
                                continue  # Try again without recursion
                        except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError):
                            # Invalid or missing lock file, remove and try again
                            try:
                                os.remove(self.lockfile_path)
                            except OSError as e:
                                logger.warning(f"Failed to remove stale lockfile {self.lockfile_path}: {e}")
                            retry_count += 1
                            continue  # Try again without recursion
                    return False
            except Exception as e:
                logger.error(f"Failed to acquire lock (attempt {retry_count + 1}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(0.1)  # Brief delay before retry
                    continue
        
        logger.error(f"Failed to acquire lock after {max_retries} attempts")
        return False

    def update_lockfile_data(self, **kwargs):
        """
        Update the lockfile with additional data.
        
        This allows adding extra fields like rsync_pid after the lock is acquired.
        
        Args:
            **kwargs: Key-value pairs to add to the lockfile
        """
        if not os.path.exists(self.lockfile_path):
            logger.warning(f"Cannot update lockfile - file doesn't exist: {self.lockfile_path}")
            return
        
        try:
            import json
            # Read current data
            with open(self.lockfile_path, 'r') as f:
                data = json.load(f)
            
            # Update with new data
            data.update(kwargs)
            
            # Write back atomically
            temp_path = self.lockfile_path + '.tmp'
            with open(temp_path, 'w') as f:
                json.dump(data, f)
            os.replace(temp_path, self.lockfile_path)
            
            logger.debug(f"Updated lockfile with: {kwargs}")
        except Exception as e:
            logger.error(f"Failed to update lockfile: {e}")

    def _setup_signal_handlers(self):
        """Setup signal handlers for cleanup on termination."""
        def cleanup_handler(signum, frame):
            logger.info(f"Received signal {signum}, cleaning up singleton lock")
            self.release_lock()
            # Restore original signal handler and re-raise
            signal.signal(signum, self._original_signal_handlers.get(signum, signal.SIG_DFL))
            os.kill(os.getpid(), signum)
        
        # Store original handlers and install our cleanup handler
        for sig in [signal.SIGTERM, signal.SIGINT]:
            self._original_signal_handlers[sig] = signal.signal(sig, cleanup_handler)

    def release_lock(self):
        """
        Release singleton lock.
        """
        # Before removing lock file, check if there's an rsync daemon to clean up
        rsync_pid = None
        if os.path.exists(self.lockfile_path):
            try:
                import json
                with open(self.lockfile_path, 'r') as f:
                    data = json.load(f)
                rsync_pid = data.get('rsync_pid')
            except Exception as e:
                logger.debug(f"Could not read rsync_pid from lockfile: {e}")
        
        if self.lockfile is not None:
            try:
                os.close(self.lockfile)
                self.lockfile = None
            except OSError as e:
                logger.warning(f"Failed to close lockfile: {e}")

        if os.path.exists(self.lockfile_path):
            try:
                os.remove(self.lockfile_path)
                logger.info(f"Released singleton lock: {self.lockfile_path}")
            except Exception as e:
                logger.warning(f"Failed to remove lock file: {e}")
        
        # Clean up rsync daemon if it exists
        if rsync_pid:
            _cleanup_rsync_daemon(rsync_pid)
        
        # Restore original signal handlers
        self._restore_signal_handlers()

    def _restore_signal_handlers(self):
        """Restore original signal handlers."""
        for sig, handler in self._original_signal_handlers.items():
            try:
                signal.signal(sig, handler)
            except Exception as e:
                logger.warning(f"Failed to restore signal handler for {sig}: {e}")

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
        import json
        with open(lockfile_path, 'r') as f:
            data = json.load(f)
        
        pid = data.get('pid')
        if not pid:
            return False

        # Check if process is still running
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # Process not running
            return False
    except (ValueError, FileNotFoundError, KeyError, json.JSONDecodeError):
        return False
