from typing import List, Optional, Tuple
import logging

from scheduler.core.config import Config
from scheduler.core.models import Job, Node
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager

logger = logging.getLogger(__name__)


class Scheduler:
    """Job scheduling algorithm"""

    def __init__(
        self,
        job_manager: JobManager,
        node_manager: NodeManager,
        config: Config
    ):
        """
        Initialize scheduler.

        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        self.job_manager = job_manager
        self.node_manager = node_manager
        self.config = config

    def schedule_cycle(self):
        """
        Run one scheduling cycle.
        Evaluates pending jobs and assigns to available nodes.
        """
        # Get pending jobs sorted by priority
        pending_jobs = self.job_manager.get_pending_jobs()

        if not pending_jobs:
            return

        # Get completed job IDs for dependency checking
        completed_job_ids = self.job_manager.get_completed_job_ids()

        # Try to schedule each pending job
        scheduled_count = 0
        for job in pending_jobs:
            # Check if dependencies are satisfied
            if not job.can_start(completed_job_ids):
                logger.debug(f"Job {job.job_id} waiting for dependencies")
                continue

            # Try to schedule the job
            if self.try_schedule_job(job):
                scheduled_count += 1

        if scheduled_count > 0:
            logger.info(f"Scheduled {scheduled_count} job(s) in this cycle")

    def try_schedule_job(self, job: Job) -> bool:
        """
        Try to schedule a single job.

        Args:
            job: Job to schedule

        Returns:
            True if job was successfully scheduled
        """
        # Find suitable node
        result = self.find_suitable_node(job)
        if not result:
            logger.debug(f"No suitable node found for job {job.job_id}")
            return False

        node_name, gpu_ids = result

        # Start grace period on the node
        self.node_manager.start_node_grace_period(node_name)

        # Mark job as started
        # Note: We only suggest GPUs via CUDA_VISIBLE_DEVICES, not enforce assignments
        # GPU availability is determined by actual usage monitoring via pynvml
        self.job_manager.start_job(job.job_id, node_name, gpu_ids)

        logger.info(f"Job {job.job_id} scheduled on {node_name} with GPUs {gpu_ids}")
        return True

    def find_suitable_node(self, job: Job) -> Optional[Tuple[str, List[int]]]:
        """
        Find a suitable node for a job.

        Args:
            job: Job to find node for

        Returns:
            Tuple of (node_name, gpu_ids) if found, None otherwise
        """
        # Get connected nodes
        nodes = self.node_manager.get_connected_nodes()

        # Check each requirement alternative
        for req_node, req_gpus in job.requirements.alternatives:
            # Filter nodes by requirement
            candidate_nodes = nodes if req_node is None else [
                n for n in nodes if n.node_name == req_node
            ]

            # Try each candidate node
            for node in candidate_nodes:
                # Skip if node is in grace period
                if node.is_in_grace_period():
                    continue

                # Get free and stable GPUs
                free_gpus = node.get_free_gpus(
                    self.config.worker.gpu_util_threshold,
                    self.config.worker.gpu_mem_threshold,
                    self.config.worker.gpu_stable_time
                )

                # Check if enough GPUs are available
                if len(free_gpus) >= req_gpus:
                    # Take the required number of GPUs
                    selected_gpus = free_gpus[:req_gpus]
                    return (node.node_name, selected_gpus)

        # No suitable node found
        return None
