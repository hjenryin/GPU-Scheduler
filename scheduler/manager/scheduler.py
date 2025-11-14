from typing import List, Optional, Tuple
import logging
from datetime import datetime

from scheduler.core import Config
from scheduler.core import Job, Node
from scheduler.manager.job_manager import JobManager
from scheduler.manager.node_manager import NodeManager

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
        logger.debug(f"Scheduler cycle: {len(pending_jobs)} pending jobs")

        if not pending_jobs:
            logger.debug("No pending jobs to schedule")
            return

        # Get completed job IDs for dependency checking
        completed_job_ids = self.job_manager.get_completed_job_ids()
        logger.debug(f"Completed job IDs: {completed_job_ids}")

        # Try to schedule each pending job
        scheduled_count = 0
        for job in pending_jobs:
            logger.debug(f"Attempting to schedule job {job.job_id}")
            # Check if dependencies are satisfied
            if not job.can_start(completed_job_ids):
                logger.debug(f"Job {job.job_id} waiting for dependencies")
                continue

            # Try to schedule the job
            if self.try_schedule_job(job):
                scheduled_count += 1
                logger.debug(f"Successfully scheduled job {job.job_id}")
            else:
                logger.debug(f"Failed to schedule job {job.job_id}")

        if scheduled_count > 0:
            logger.info(f"Scheduled {scheduled_count} job(s) in this cycle")
        else:
            logger.debug("No jobs were scheduled in this cycle")

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

        Supports:
        - Fixed count: "gpu1:4" - allocate exactly 4 GPUs
        - Range: "gpu1:4-8" - allocate 4-8 GPUs (prefer more)
        - Flexible: "gpu1" - allocate all available GPUs
        - Repeated hosts: "gpu1:4,gpu1:8" - prefer more GPUs when available

        Args:
            job: Job to find node for

        Returns:
            Tuple of (node_name, gpu_ids) if found, None otherwise
        """
        # Get connected nodes
        nodes = self.node_manager.get_connected_nodes()
        logger.debug(f"Found {len(nodes)} connected nodes")

        # Group alternatives by node name to handle repeated hosts
        # For each node, collect all possible GPU counts and find the best match
        from collections import defaultdict
        node_requirements = defaultdict(list)

        for req_node, min_gpus, max_gpus in job.requirements.alternatives:
            node_requirements[req_node].append((min_gpus, max_gpus))

        # Try each unique node (or None for any node)
        for req_node, gpu_options in node_requirements.items():
            logger.debug(f"Checking node '{req_node}' with {len(gpu_options)} options: {gpu_options}")

            # Filter nodes by requirement
            candidate_nodes = nodes if req_node is None else [
                n for n in nodes if n.node_name == req_node
            ]
            logger.debug(f"Found {len(candidate_nodes)} candidate nodes")

            # Try each candidate node
            for node in candidate_nodes:
                logger.debug(f"Checking node {node.node_name}")
                # Skip if node is in grace period
                if node.is_in_grace_period():
                    logger.debug(f"Node {node.node_name} is in grace period, skipping")
                    continue

                # Get free and stable GPUs
                free_gpus = node.get_free_gpus(
                    self.config.worker.gpu_util_threshold,
                    self.config.worker.gpu_mem_threshold,
                    self.config.worker.gpu_stable_time
                )
                logger.debug(f"Node {node.node_name} has {len(free_gpus)} free GPUs: {free_gpus}")

                # Find the best matching option for this node
                # Sort options by max_gpus descending to prefer more GPUs
                sorted_options = sorted(gpu_options, key=lambda x: (x[1] if x[1] != -1 else float('inf')), reverse=True)

                for min_gpus, max_gpus in sorted_options:
                    logger.debug(f"  Trying option: min={min_gpus}, max={max_gpus}")

                    if max_gpus == -1:
                        # Flexible allocation: take all available GPUs
                        if len(free_gpus) >= min_gpus:
                            selected_gpus = free_gpus  # Take ALL available GPUs
                            logger.debug(f"Flexible allocation: selected all {len(selected_gpus)} GPUs {selected_gpus} for job {job.job_id}")
                            return (node.node_name, selected_gpus)
                        else:
                            logger.debug(f"Node {node.node_name} has insufficient GPUs for flexible allocation: need {min_gpus}, have {len(free_gpus)}")
                    elif min_gpus == max_gpus:
                        # Fixed allocation: need exact count
                        if len(free_gpus) >= min_gpus:
                            selected_gpus = free_gpus[:min_gpus]
                            logger.debug(f"Fixed allocation: selected {len(selected_gpus)} GPUs {selected_gpus} for job {job.job_id}")
                            return (node.node_name, selected_gpus)
                        else:
                            logger.debug(f"Node {node.node_name} has insufficient GPUs: need {min_gpus}, have {len(free_gpus)}")
                    else:
                        # Range allocation: take as many as available within range
                        if len(free_gpus) >= min_gpus:
                            num_to_allocate = min(len(free_gpus), max_gpus)
                            selected_gpus = free_gpus[:num_to_allocate]
                            logger.debug(f"Range allocation: selected {len(selected_gpus)} GPUs {selected_gpus} for job {job.job_id} (min={min_gpus}, max={max_gpus})")
                            return (node.node_name, selected_gpus)
                        else:
                            logger.debug(f"Node {node.node_name} has insufficient GPUs for range: need {min_gpus}, have {len(free_gpus)}")

        # No suitable node found
        logger.debug(f"No suitable node found for job {job.job_id}")
        return None
