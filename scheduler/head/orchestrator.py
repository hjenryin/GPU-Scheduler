from scheduler.core.config import Config


class Orchestrator:
    """Main head node orchestrator"""

    def __init__(self, config: Config):
        """
        Initialize orchestrator.
        
        Args:
            config: Configuration instance
        """
        pass

    def start(self):
        """
        Start the orchestrator and all components.
        
        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        pass

    def stop(self, graceful: bool = True):
        """
        Stop the orchestrator and all components.
        
        Args:
            graceful: If True, wait for jobs to complete
        """
        pass

    def run(self):
        """
        Run the orchestrator main loop (blocking).
        """
        pass

    def get_status(self) -> dict:
        """
        Get overall cluster status.
        
        Returns:
            Dictionary containing cluster status
        """
        pass
