import os
import signal
import subprocess
import logging
from typing import List, Optional, Tuple, Dict

from scheduler.core.config import Config
from scheduler.core.models import Job
from scheduler.core.exceptions import JobNotFoundException
from scheduler.worker.file_handler import FileHandler
from scheduler.worker.git_snapshot import GitSnapshotManager

logger = logging.getLogger(__name__)


class JobExecutor:
    """Executes jobs as subprocesses"""

    def __init__(self, config: Config):
        """
        Initialize job executor.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.file_handler = FileHandler(config)
        self.git_snapshot = GitSnapshotManager(config)
        self.processes: Dict[int, subprocess.Popen] = {}  # pid -> Popen object
        self.job_worktrees: Dict[str, str] = {}  # job_id -> worktree_path

        logger.info("JobExecutor initialized")

    def execute_job(self, job: Job, gpu_ids: List[int]) -> int:
        """
        Execute a job.

        Args:
            job: Job to execute
            gpu_ids: GPU IDs assigned to this job

        Returns:
            Process ID of running job

        Raises:
            RuntimeError: If job execution fails
        """
        try:
            # Set up environment variables
            env = os.environ.copy()

            # Add CUDA_VISIBLE_DEVICES
            env['CUDA_VISIBLE_DEVICES'] = ','.join(map(str, gpu_ids))

            # Add user-specified env vars
            if job.env_vars:
                logger.info(f"[TRACE] Job {job.job_id}: Adding environment variables: {job.env_vars}")
                env.update(job.env_vars)
                logger.info(f"[TRACE] Job {job.job_id}: Final environment: {dict(env)}")
            else:
                logger.info(f"[TRACE] Job {job.job_id}: No environment variables specified")

            # Determine working directory and script path
            # If job has a snapshot, restore it to a worktree
            if job.snapshot_ref and job.snapshot_working_dir:
                logger.info(f"Job {job.job_id} has snapshot {job.snapshot_ref}, restoring to worktree")
                
                # Create worktree directory path
                worktree_path = self.file_handler.get_job_snapshot_dir(job.job_id)
                
                # Restore snapshot to worktree
                success = self.git_snapshot.restore_snapshot(
                    job.job_id,
                    job.snapshot_ref,
                    job.snapshot_working_dir,
                    worktree_path
                )
                
                if success:
                    # Store worktree path for cleanup
                    self.job_worktrees[job.job_id] = worktree_path
                    
                    # Use worktree as working directory
                    working_dir = worktree_path
                    
                    # Reconstruct script path relative to worktree
                    # Script might be in subdirectories, so preserve relative structure
                    try:
                        # Get script path relative to original working dir
                        rel_script_path = os.path.relpath(job.script, job.snapshot_working_dir)
                        # Reconstruct in worktree
                        script_path = os.path.join(worktree_path, rel_script_path)
                    except ValueError:
                        # Script is outside working dir (absolute path?), use basename
                        script_basename = os.path.basename(job.script)
                        script_path = os.path.join(worktree_path, script_basename)
                    
                    logger.info(f"Job {job.job_id} will execute in worktree: {worktree_path}")
                    logger.info(f"Job {job.job_id} script path in worktree: {script_path}")
                else:
                    logger.warning(f"Failed to restore snapshot for job {job.job_id}, using original working directory")
                    working_dir = job.working_dir or os.path.dirname(os.path.abspath(job.script))
                    script_path = job.script
            else:
                # No snapshot, use original working directory
                working_dir = job.working_dir or os.path.dirname(os.path.abspath(job.script))
                script_path = job.script
                logger.info(f"Job {job.job_id} has no snapshot, using original working directory")

            # Create log file paths
            stdout_log = self.file_handler.get_job_log_path(job.job_id, stderr=False)
            stderr_log = self.file_handler.get_job_log_path(job.job_id, stderr=True)

            # Build command from script and script_args
            # Execute the command as-is without modification
            cmd = [script_path]
            if job.script_args:
                cmd.extend(job.script_args)

            logger.info(f"Executing job {job.job_id}: {script_path}")
            logger.info(f"Command: {cmd}")
            logger.info(f"Working directory: {working_dir}")
            logger.info(f"CUDA_VISIBLE_DEVICES: {env['CUDA_VISIBLE_DEVICES']}")
            logger.info(f"Stdout log: {stdout_log}")
            logger.info(f"Stderr log: {stderr_log}")

            # Ensure log directories exist
            os.makedirs(os.path.dirname(stdout_log), exist_ok=True)
            os.makedirs(os.path.dirname(stderr_log), exist_ok=True)

            # Open log files
            stdout_file = open(stdout_log, 'w')
            stderr_file = open(stderr_log, 'w')

            # Start the process
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=working_dir,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True  # Create new process group
            )
            
            # Close file handles in parent process (child process has its own copies)
            stdout_file.close()
            stderr_file.close()

            pid = process.pid
            self.processes[pid] = process

            logger.info(f"Job {job.job_id} started with PID {pid}")
            return pid
        except FileNotFoundError as e:
            # Cleanup worktree if it was created
            if job.job_id in self.job_worktrees:
                self._cleanup_job_worktree(job)
            raise RuntimeError(f"Script not found: {e}")
        except Exception as e:
            # Cleanup worktree if it was created
            if job.job_id in self.job_worktrees:
                self._cleanup_job_worktree(job)
            logger.error(f"Failed to execute job {job.job_id}: {e}")
            raise RuntimeError(f"Failed to execute job: {e}")

    def get_job_status(self, pid: int) -> Tuple[bool, Optional[int]]:
        """
        Get status of a running job.

        Args:
            pid: Process ID

        Returns:
            Tuple of (is_running, exit_code). exit_code is None if still running.
        """
        if pid in self.processes:
            process = self.processes[pid]
            return_code = process.poll()

            if return_code is None:
                # Still running
                return (True, None)
            else:
                # Finished
                # Clean up
                del self.processes[pid]
                return (False, return_code)
        else:
            # Process not tracked by us, try to check if it exists
            try:
                os.kill(pid, 0)
                # Process exists
                return (True, None)
            except OSError:
                # Process doesn't exist
                return (False, -1)  # Unknown exit code

    def terminate_job(self, pid: int):
        """
        Terminate a running job.

        Args:
            pid: Process ID
        """
        try:
            if pid in self.processes:
                process = self.processes[pid]
                process.terminate()  # SIGTERM
                logger.info(f"Terminated job with PID {pid}")
                del self.processes[pid]
            else:
                # Try to kill process directly using SIGTERM
                os.kill(pid, signal.SIGTERM)
                logger.info(f"Sent SIGTERM to PID {pid}")
        except OSError as e:
            logger.warning(f"Failed to terminate job with PID {pid}: {e}")

    def cleanup_job(self, job: Job):
        """
        Cleanup resources after job completion.
        
        This includes creating a completion snapshot (if job had a snapshot)
        and removing git worktrees.
        
        Args:
            job: Job to cleanup
        """
        if job.job_id in self.job_worktrees:
            # Create completion snapshot before cleanup
            worktree_path = self.job_worktrees[job.job_id]
            if job.snapshot_ref and job.snapshot_working_dir:
                try:
                    logger.info(f"Creating completion snapshot for job {job.job_id}")
                    completion_ref = self.git_snapshot.create_snapshot(
                        f"{job.job_id}-completion",
                        worktree_path
                    )
                    if completion_ref:
                        logger.info(f"Created completion snapshot {completion_ref} for job {job.job_id}")
                    else:
                        logger.warning(f"Failed to create completion snapshot for job {job.job_id}")
                except Exception as e:
                    logger.warning(f"Error creating completion snapshot for job {job.job_id}: {e}")
            
            # Now cleanup the worktree
            self._cleanup_job_worktree(job)
    
    def _cleanup_job_worktree(self, job: Job):
        """
        Internal method to cleanup git worktree for a job.
        
        Args:
            job: Job to cleanup worktree for
        """
        if job.job_id not in self.job_worktrees:
            return
        
        worktree_path = self.job_worktrees[job.job_id]
        
        try:
            if job.snapshot_ref and job.snapshot_working_dir:
                self.git_snapshot.cleanup_snapshot(
                    job.job_id,
                    job.snapshot_ref,
                    job.snapshot_working_dir,
                    worktree_path
                )
                logger.info(f"Cleaned up worktree for job {job.job_id}")
            
            # Remove from tracking
            del self.job_worktrees[job.job_id]
        except Exception as e:
            logger.warning(f"Error cleaning up worktree for job {job.job_id}: {e}")

    def get_job_logs(
        self,
        job_id: str,
        lines: Optional[int] = None,
        stderr: bool = False
    ) -> str:
        """
        Get job logs.

        Args:
            job_id: Job ID
            lines: Number of lines from end (None for all)
            stderr: If True, return stderr instead of stdout

        Returns:
            Log contents as string

        Raises:
            JobNotFoundException: If job logs not found
        """
        log_path = self.file_handler.get_job_log_path(job_id, stderr=stderr)

        if not os.path.exists(log_path):
            raise JobNotFoundException(f"Log file not found for job {job_id}")

        try:
            with open(log_path, 'r') as f:
                if lines is None:
                    # Return all lines
                    return f.read()
                else:
                    # Return last N lines
                    all_lines = f.readlines()
                    return ''.join(all_lines[-lines:])
        except Exception as e:
            logger.error(f"Failed to read logs for job {job_id}: {e}")
            raise JobNotFoundException(f"Failed to read logs: {e}")
