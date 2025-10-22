from abc import ABC, abstractmethod
from typing import List, Optional

from scheduler.core.models import Job, Node


class StorageBackend(ABC):
    """Abstract base class for storage backends"""

    @abstractmethod
    def save_job(self, job: Job):
        """Save job to storage"""
        pass
    
    @abstractmethod
    def load_job(self, job_id: str) -> Optional[Job]:
        """Load job from storage"""
        pass
    
    @abstractmethod
    def load_all_jobs(self) -> List[Job]:
        """Load all jobs from storage"""
        pass
    
    @abstractmethod
    def delete_job(self, job_id: str):
        """Delete job from storage"""
        pass
    
    @abstractmethod
    def save_node(self, node: Node):
        """Save node to storage"""
        pass
    
    @abstractmethod
    def load_node(self, node_name: str) -> Optional[Node]:
        """Load node from storage"""
        pass
    
    @abstractmethod
    def load_all_nodes(self) -> List[Node]:
        """Load all nodes from storage"""
        pass
    
    @abstractmethod
    def close(self):
        """Close storage backend and cleanup resources"""
        pass
