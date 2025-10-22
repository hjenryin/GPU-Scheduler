from typing import List, Optional
from scheduler.core.config import Config
from scheduler.core.models import Job, Node
from scheduler.storage import StorageBackend


class PersistenceManager:
    """Manages state persistence"""

    def __init__(self, backend: 'StorageBackend', config: Config):
        """
        Initialize persistence manager.
        
        Args:
            backend: StorageBackend instance
            config: Configuration instance
        """
        pass

    def save_job(self, job: Job):
        """
        Save job to storage.
        
        Args:
            job: Job to save
        """
        pass

    def load_job(self, job_id: str) -> Optional[Job]:
        """
        Load job from storage.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance if found, None otherwise
        """
        pass

    def load_all_jobs(self) -> List[Job]:
        """
        Load all jobs from storage.
        
        Returns:
            List of Job instances
        """
        pass

    def delete_job(self, job_id: str):
        """
        Delete job from storage.
        
        Args:
            job_id: Job ID
        """
        pass

    def save_node(self, node: Node):
        """
        Save node to storage.
        
        Args:
            node: Node to save
        """
        pass

    def load_node(self, node_name: str) -> Optional[Node]:
        """
        Load node from storage.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance if found, None otherwise
        """
        pass

    def load_all_nodes(self) -> List[Node]:
        """
        Load all nodes from storage.
        
        Returns:
            List of Node instances
        """
        pass

    def checkpoint(self):
        """
        Create a checkpoint of current state.
        """
        pass
