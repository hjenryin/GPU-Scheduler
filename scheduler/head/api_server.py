from scheduler.head import JobManager, NodeManager
from scheduler.core import Config
from fastapi import FastAPI

class APIServer:
    """HTTP API server using FastAPI"""

    def __init__(
        self,
        job_manager: JobManager,
        node_manager: NodeManager,
        config: Config
    ):
        """
        Initialize API server.
        
        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        pass

    def start(self):
        """
        Start the API server.
        
        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        pass

    def stop(self):
        """
        Stop the API server.
        """
        pass

    def get_app(self) -> 'FastAPI':
        """
        Get FastAPI application instance.
        
        Returns:
            FastAPI app
        """
        pass
