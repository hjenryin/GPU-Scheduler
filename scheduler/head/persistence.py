from typing import List, Optional
import logging

from scheduler.core.config import Config
from scheduler.core.models import Job, Node
from scheduler.storage.backend import StorageBackend

logger = logging.getLogger(__name__)


class PersistenceManager:
    """Manages state persistence"""

    def __init__(self, backend: StorageBackend, config: Config):
        """
        Initialize persistence manager.

        Args:
            backend: StorageBackend instance
            config: Configuration instance
        """
        self.backend = backend
        self.config = config

    def save_job(self, job: Job):
        """
        Save job to storage.

        Args:
            job: Job to save
        """
        try:
            self.backend.save_job(job)
        except Exception as e:
            logger.error(f"Failed to save job {job.job_id}: {e}")
            raise

    def load_job(self, job_id: str) -> Optional[Job]:
        """
        Load job from storage.

        Args:
            job_id: Job ID

        Returns:
            Job instance if found, None otherwise
        """
        try:
            return self.backend.load_job(job_id)
        except Exception as e:
            logger.error(f"Failed to load job {job_id}: {e}")
            return None

    def load_all_jobs(self) -> List[Job]:
        """
        Load all jobs from storage.

        Returns:
            List of Job instances
        """
        try:
            return self.backend.load_all_jobs()
        except Exception as e:
            logger.error(f"Failed to load all jobs: {e}")
            return []

    def delete_job(self, job_id: str):
        """
        Delete job from storage.

        Args:
            job_id: Job ID
        """
        try:
            self.backend.delete_job(job_id)
        except Exception as e:
            logger.error(f"Failed to delete job {job_id}: {e}")
            raise

    def save_node(self, node: Node):
        """
        Save node to storage.

        Args:
            node: Node to save
        """
        try:
            self.backend.save_node(node)
        except Exception as e:
            logger.error(f"Failed to save node {node.node_name}: {e}")
            raise

    def load_node(self, node_name: str) -> Optional[Node]:
        """
        Load node from storage.

        Args:
            node_name: Node name

        Returns:
            Node instance if found, None otherwise
        """
        try:
            return self.backend.load_node(node_name)
        except Exception as e:
            logger.error(f"Failed to load node {node_name}: {e}")
            return None

    def load_all_nodes(self) -> List[Node]:
        """
        Load all nodes from storage.

        Returns:
            List of Node instances
        """
        try:
            return self.backend.load_all_nodes()
        except Exception as e:
            logger.error(f"Failed to load all nodes: {e}")
            return []

    def checkpoint(self):
        """
        Create a checkpoint of current state.
        """
        # For simple backends, this is a no-op
        # For more complex scenarios, could trigger a flush or backup
        logger.debug("Checkpoint created")
