from typing import List, Optional, Set, Dict

from scheduler.core.exceptions import InvalidRequirementException
from scheduler.core.models import Job, JobStatus
from scheduler.storage import StorageBackend
from scheduler.core.config import Config
from scheduler.head import PersistenceManager

class JobManager:
    """Manages job queue and lifecycle"""

    def __init__(self, persistence: 'PersistenceManager', config: Config):
        """
        Initialize job manager.
        
        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        pass

    def submit_job(
        self,
        script: str,
        requirements: str,
        name: Optional[str] = None,
        script_args: List[str] = None,
        working_dir: Optional[str] = None,
        env_vars: Dict[str, str] = None,
        dependencies: List[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None
    ) -> Job:
        """
        Submit a new job.
        
        Args:
            script: Path to script
            requirements: Requirement string
            name: Job name
            script_args: Script arguments
            working_dir: Working directory
            env_vars: Environment variables
            dependencies: Job dependencies
            priority: Job priority
            timeout: Job timeout
            
        Returns:
            Created Job instance
            
        Raises:
            ValidationException: If parameters are invalid
        """
        pass

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance if found, None otherwise
        """
        pass

    def list_jobs(
        self,
        status_filter: Optional[JobStatus] = None,
        limit: Optional[int] = None
    ) -> List[Job]:
        """
        List jobs with optional filtering.
        
        Args:
            status_filter: Filter by job status
            limit: Maximum number of jobs to return
            
        Returns:
            List of Job instances
        """
        pass

    def get_pending_jobs(self) -> List[Job]:
        """
        Get all pending jobs sorted by priority.
        
        Returns:
            List of pending Job instances
        """
        pass

    def get_running_jobs(self) -> List[Job]:
        """
        Get all running jobs.
        
        Returns:
            List of running Job instances
        """
        pass

    def get_completed_job_ids(self) -> Set[str]:
        """
        Get set of completed job IDs.
        
        Returns:
            Set of job IDs that are completed
        """
        pass

    def start_job(self, job_id: str, node_name: str, gpu_ids: List[int]):
        """
        Mark job as started.
        
        Args:
            job_id: Job ID
            node_name: Node where job is starting
            gpu_ids: GPUs assigned to job
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass

    def complete_job(self, job_id: str, exit_code: int):
        """
        Mark job as completed.
        
        Args:
            job_id: Job ID
            exit_code: Process exit code
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass

    def fail_job(self, job_id: str, error_message: str):
        """
        Mark job as failed.
        
        Args:
            job_id: Job ID
            error_message: Error message
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass

    def cancel_job(self, job_id: str):
        """
        Cancel a job.
        
        Args:
            job_id: Job ID
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass
