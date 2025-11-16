import os
import signal
import subprocess
import logging
from typing import List, Optional, Tuple, Dict

from scheduler.core import Config
from scheduler.core import Job
from scheduler.core import JobNotFoundException
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
                env.update(job.env_vars)

            # Determine working directory and script path
            # If job has a snapshot (created by client at submission time), restore it to a worktree
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
                    
                    # Calculate the working directory within the worktree
                    # The worktree contains the entire workspace from snapshot_working_dir
                    # We need to find the subdirectory that corresponds to job.working_dir
                    try:
                        # Get relative path from workspace root to job working dir
                        rel_working_dir = os.path.relpath(job.working_dir, job.snapshot_working_dir)
                        # Reconstruct working dir in worktree
                        if rel_working_dir == '.':
                            # Job was submitted from workspace root
                            working_dir = worktree_path
                        else:
                            # Job was submitted from subdirectory
                            working_dir = os.path.join(worktree_path, rel_working_dir)
                    except ValueError:
                        # working_dir is outside snapshot_working_dir, use worktree root
                        logger.warning(f"Job working_dir {job.working_dir} is outside snapshot root {job.snapshot_working_dir}, using worktree root")
                        working_dir = worktree_path
                    
                    logger.info(f"Job {job.job_id} will execute in worktree: {working_dir}")
                else:
                    logger.warning(f"Failed to restore snapshot for job {job.job_id}, using original working directory")
                    working_dir = job.working_dir
            else:
                # No snapshot, use original working directory
                # Assert working_dir is not None (validated at Job construction)
                assert job.working_dir is not None, f"Job {job.job_id}: working_dir must not be None"
                working_dir = job.working_dir
                logger.info(f"Job {job.job_id} has no snapshot, using working directory: {working_dir}")

            # Clean up old log files (older than 24 hours) before starting new job
            self.file_handler.cleanup_old_logs(max_age_hours=24)

            # Create log file paths
            stdout_log = self.file_handler.get_job_log_path(job.job_id, stderr=False)
            stderr_log = self.file_handler.get_job_log_path(job.job_id, stderr=True)

            # Use job command directly
            cmd_parts = job.command

            # Ensure log directories exist
            os.makedirs(os.path.dirname(stdout_log), exist_ok=True)
            os.makedirs(os.path.dirname(stderr_log), exist_ok=True)

            # Build the complete command string with output redirection
            # This ensures output is written immediately without buffering issues
            cmd_str = ' '.join(cmd_parts)
            bash_cmd = f"{cmd_str} > {stdout_log} 2> {stderr_log}"

            # Wrap with conda run if conda environment is specified
            # Use bash -c to handle redirection AFTER conda activates the environment
            # This avoids conda's output buffering that causes log loss on early termination
            if job.conda_env:
                conda_cmd = self.config.conda.command
                cmd = [conda_cmd, 'run', '-n', job.conda_env, 'bash', '-c', bash_cmd]
                logger.info(f"Running job {job.job_id} in conda environment '{job.conda_env}'")
            else:
                cmd = ['bash', '-c', bash_cmd]

            logger.info(f"Executing job {job.job_id}")
            logger.info(f"Command: {cmd_str}")
            logger.info(f"Working directory: {working_dir}")
            logger.info(f"CUDA_VISIBLE_DEVICES: {env['CUDA_VISIBLE_DEVICES']}")
            logger.info(f"Stdout log: {stdout_log}")
            logger.info(f"Stderr log: {stderr_log}")

            # Start the process with output redirection handled by bash
            # Don't pass stdout/stderr to Popen - they're handled by the bash command
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=working_dir,
                start_new_session=True  # Create new process group
            )

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
        Terminate a running job and all its child processes.

        Since jobs are started with start_new_session=True, they run in their own
        process group. We need to kill the entire process group to ensure all
        child processes are terminated.

        Args:
            pid: Process ID (also the process group ID due to start_new_session=True)
        """
        try:
            if pid in self.processes:
                process = self.processes[pid]
                # Kill the entire process group
                try:
                    os.killpg(pid, signal.SIGTERM)
                    logger.info(f"Terminated process group {pid} (SIGTERM)")
                except ProcessLookupError:
                    # Process group already dead
                    logger.info(f"Process group {pid} already terminated")
                except PermissionError:
                    # Fallback to single process kill
                    process.terminate()
                    logger.warning(f"Cannot kill process group {pid}, terminated parent process only")
                del self.processes[pid]
            else:
                # Try to kill process group directly using SIGTERM
                try:
                    os.killpg(pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to process group {pid}")
                except ProcessLookupError:
                    logger.info(f"Process group {pid} not found (already terminated)")
                except PermissionError:
                    # Fallback to single process
                    os.kill(pid, signal.SIGTERM)
                    logger.warning(f"Cannot kill process group {pid}, sent SIGTERM to process only")
        except OSError as e:
            logger.warning(f"Failed to terminate job with PID {pid}: {e}")

    def cleanup_job(self, job: Job) -> Optional[str]:
        """
        Cleanup resources after job completion.

        This creates an "after" commit capturing changes made during execution,
        then removes git worktrees.

        Args:
            job: Job to cleanup

        Returns:
            Commit SHA of the "after" commit, or None if no worktree or on error
        """
        if job.job_id in self.job_worktrees:
            # Cleanup the worktree and get after commit
            return self._cleanup_job_worktree(job)
        return None

    def _cleanup_job_worktree(self, job: Job) -> Optional[str]:
        """
        Internal method to cleanup git worktree for a job.

        Args:
            job: Job to cleanup worktree for

        Returns:
            Commit SHA of the "after" commit, or None if no worktree or on error
        """
        if job.job_id not in self.job_worktrees:
            return None

        worktree_path = self.job_worktrees[job.job_id]
        after_commit_ref = None

        try:
            if job.snapshot_ref and job.snapshot_working_dir:
                after_commit_ref = self.git_snapshot.cleanup_snapshot(
                    job.job_id,
                    job.snapshot_ref,
                    job.snapshot_working_dir,
                    worktree_path
                )
                if after_commit_ref:
                    logger.info(f"Created after commit {after_commit_ref} and cleaned up worktree for job {job.job_id}")
                else:
                    logger.info(f"Cleaned up worktree for job {job.job_id} (no after commit created)")

            # Remove from tracking
            del self.job_worktrees[job.job_id]
            return after_commit_ref
        except Exception as e:
            logger.warning(f"Error cleaning up worktree for job {job.job_id}: {e}")
            return None

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
