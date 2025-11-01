from typing import List, Optional, Set, Dict
import logging
from datetime import datetime
import os

from scheduler.core.exceptions import InvalidRequirementException, JobNotFoundException
from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.core.config import Config
from scheduler.core.utils import generate_job_id
from scheduler.head.persistence import PersistenceManager
from scheduler.worker.git_snapshot import GitSnapshotManager

logger = logging.getLogger(__name__)


class JobManager:
    """Manages job queue and lifecycle"""

    def __init__(self, persistence: PersistenceManager, config: Config):
        """
        Initialize job manager.

        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        self.persistence = persistence
        self.config = config
        self.jobs: Dict[str, Job] = {}

        # Load existing jobs from storage
        self._load_jobs()

    def _load_jobs(self):
        """Load jobs from storage into memory"""
        jobs = self.persistence.load_all_jobs()
        for job in jobs:
            self.jobs[job.job_id] = job
        logger.info(f"Loaded {len(jobs)} jobs from storage")

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

        Returns:
            Created Job instance

        Raises:
            ValidationException: If parameters are invalid
        """
        # Parse requirements to validate
        job_requirements = JobRequirement(requirements)

        # Generate job ID and name
        job_id = generate_job_id()
        job_name = name or os.path.basename(script)

        # Use current directory if not specified
        if working_dir is None:
            working_dir = os.getcwd()

        # Create job
        logger.info(f"[TRACE] Creating job {job_id} with env_vars: {env_vars}")
        job = Job(
            job_id=job_id,
            name=job_name,
            script=script,
            requirements=job_requirements,
            script_args=script_args,
            working_dir=working_dir,
            env_vars=env_vars,
            dependencies=dependencies,
            priority=priority,
            submitted_at=datetime.now(),
            status=JobStatus.PENDING
        )
        logger.info(f"[TRACE] Job {job_id} created with env_vars: {job.env_vars}")

        # Create git snapshot using shadow repository
        # This always creates snapshots regardless of whether working_dir is in a git repo
        try:
            git_manager = GitSnapshotManager(self.config)
            snapshot_ref = git_manager.create_snapshot(job_id, working_dir)
            if snapshot_ref:
                job.snapshot_ref = snapshot_ref
                job.snapshot_working_dir = working_dir
                logger.info(f"Created git snapshot {snapshot_ref} for job {job_id}")
            else:
                logger.debug(f"No snapshot created for job {job_id} (error or no files to snapshot)")
        except Exception as e:
            # Don't fail job submission if snapshot creation fails
            logger.warning(f"Failed to create snapshot for job {job_id}: {e}")

        # Store in memory and persist
        self.jobs[job_id] = job
        self.persistence.save_job(job)

        logger.info(f"Job {job_id} ({job_name}) submitted")
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job instance if found, None otherwise
        """
        return self.jobs.get(job_id)

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
        jobs = list(self.jobs.values())

        # Apply status filter
        if status_filter is not None:
            jobs = [j for j in jobs if j.status == status_filter]

        # Sort by submission time (newest first)
        jobs.sort(key=lambda j: j.submitted_at, reverse=True)

        # Apply limit
        if limit is not None:
            jobs = jobs[:limit]

        return jobs

    def get_pending_jobs(self) -> List[Job]:
        """
        Get all pending jobs sorted by priority.

        Returns:
            List of pending Job instances
        """
        pending = [j for j in self.jobs.values() if j.status == JobStatus.PENDING]
        # Sort by priority (higher first), then by submission time (older first)
        pending.sort(key=lambda j: (-j.priority, j.submitted_at))
        return pending

    def get_running_jobs(self) -> List[Job]:
        """
        Get all running jobs.

        Returns:
            List of running Job instances
        """
        return [j for j in self.jobs.values() if j.status == JobStatus.RUNNING]

    def get_completed_job_ids(self) -> Set[str]:
        """
        Get set of completed job IDs.

        Returns:
            Set of job IDs that are completed
        """
        return {j.job_id for j in self.jobs.values() if j.status == JobStatus.COMPLETED}

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
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        logger.info(f"[TRACE] Starting job {job_id} on node {node_name} with GPUs {gpu_ids}, env_vars: {job.env_vars}")
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        job.assigned_node = node_name
        job.assigned_gpus = gpu_ids

        self.persistence.save_job(job)
        logger.info(f"[TRACE] Job {job_id} marked as RUNNING on {node_name} with GPUs {gpu_ids}")

    def complete_job(self, job_id: str, exit_code: int):
        """
        Mark job as completed.

        Args:
            job_id: Job ID
            exit_code: Process exit code

        Raises:
            JobNotFoundException: If job not found
        """
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now()
        job.exit_code = exit_code

        self.persistence.save_job(job)
        logger.info(f"Job {job_id} completed with exit code {exit_code}")

    def fail_job(self, job_id: str, error_message: str):
        """
        Mark job as failed.

        Args:
            job_id: Job ID
            error_message: Error message

        Raises:
            JobNotFoundException: If job not found
        """
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        job.status = JobStatus.FAILED
        job.completed_at = datetime.now()
        job.error_message = error_message

        self.persistence.save_job(job)
        logger.error(f"Job {job_id} failed: {error_message}")

    def cancel_job(self, job_id: str):
        """
        Cancel a job.

        Args:
            job_id: Job ID

        Raises:
            JobNotFoundException: If job not found
        """
        job = self.jobs.get(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now()

        self.persistence.save_job(job)
        logger.info(f"Job {job_id} cancelled")
