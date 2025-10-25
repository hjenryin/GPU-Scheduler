import os
import signal
import subprocess
import logging
from typing import List, Optional, Tuple, Dict

from scheduler.core.config import Config
from scheduler.core.models import Job
from scheduler.core.exceptions import JobNotFoundException
from scheduler.worker.file_handler import FileHandler

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
        self.processes: Dict[int, subprocess.Popen] = {}  # pid -> Popen object

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

            # Determine working directory
            working_dir = job.working_dir or os.path.dirname(os.path.abspath(job.script))

            # Create log file paths
            stdout_log = self.file_handler.get_job_log_path(job.job_id, stderr=False)
            stderr_log = self.file_handler.get_job_log_path(job.job_id, stderr=True)

            # Open log files
            stdout_file = open(stdout_log, 'w')
            stderr_file = open(stderr_log, 'w')

            # Build command - use python explicitly for .py files
            import sys
            if job.script.endswith('.py'):
                cmd = [sys.executable, job.script]
            else:
                cmd = [job.script]
            if job.script_args:
                cmd.extend(job.script_args)

            logger.info(f"Executing job {job.job_id}: {job.script}")
            logger.info(f"Command: {cmd}")
            logger.info(f"Working directory: {working_dir}")
            logger.info(f"CUDA_VISIBLE_DEVICES: {env['CUDA_VISIBLE_DEVICES']}")
            logger.info(f"Stdout log: {stdout_log}")
            logger.info(f"Stderr log: {stderr_log}")

            # Start the process
            process = subprocess.Popen(
                cmd,
                env=env,
                cwd=working_dir,
                stdout=stdout_file,
                stderr=stderr_file,
                start_new_session=True  # Create new process group
            )

            pid = process.pid
            self.processes[pid] = process

            logger.info(f"Job {job.job_id} started with PID {pid}")
            return pid
        except FileNotFoundError as e:
            raise RuntimeError(f"Script not found: {e}")
        except Exception as e:
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
