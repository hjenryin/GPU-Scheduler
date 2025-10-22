from typing import List, Optional, Tuple

from scheduler.core.config import Config
from scheduler.core.models import Job, Node
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager


class Scheduler:
    """Job scheduling algorithm"""

    def __init__(
        self,
        job_manager: 'JobManager',
        node_manager: 'NodeManager',
        config: Config
    ):
        """
        Initialize scheduler.
        
        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        pass

    def schedule_cycle(self):
        """
        Run one scheduling cycle.
        Evaluates pending jobs and assigns to available nodes.
        """
        pass

    def try_schedule_job(self, job: Job) -> bool:
        """
        Try to schedule a single job.
        
        Args:
            job: Job to schedule
            
        Returns:
            True if job was successfully scheduled
        """
        pass

    def find_suitable_node(self, job: Job) -> Optional[Tuple[str, List[int]]]:
        """
        Find a suitable node for a job.
        
        Args:
            job: Job to find node for
            
        Returns:
            Tuple of (node_name, gpu_ids) if found, None otherwise
        """
        pass
