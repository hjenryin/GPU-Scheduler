from typing import List, Optional, Tuple

from scheduler.core.config import Config
from scheduler.core.models import Job


class JobExecutor:
    """Executes jobs as subprocesses"""

    def __init__(self, config: Config):
        """
        Initialize job executor.
        
        Args:
            config: Configuration instance
        """
        pass

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
        pass

    def get_job_status(self, pid: int) -> Tuple[bool, Optional[int]]:
        """
        Get status of a running job.
        
        Args:
            pid: Process ID
            
        Returns:
            Tuple of (is_running, exit_code). exit_code is None if still running.
        """
        pass

    def terminate_job(self, pid: int, force: bool = False):
        """
        Terminate a running job.
        
        Args:
            pid: Process ID
            force: If True, use SIGKILL instead of SIGTERM
        """
        pass

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
        pass
