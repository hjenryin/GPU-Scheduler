from typing import Iterator, List, Optional, Dict

from scheduler.core.exceptions import (
    ConnectionException,
    JobNotFoundException,
    NodeNotFoundException,
)
from scheduler.core.models import GPU, Job, JobStatus, Node, GPUStats

from scheduler.core.config import Config
class SchedulerClient:
    """HTTP client for scheduler API"""

    def __init__(self, address: Optional[str] = None, config: Optional[Config] = None):
        """
        Initialize scheduler client.
        
        Args:
            address: Head node address (host:port). Auto-detect if None.
            config: Configuration instance (load default if None)
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
        Submit a job.
        
        Args:
            (same as JobManager.submit_job)
            
        Returns:
            Created Job instance
            
        Raises:
            ConnectionException: If cannot connect to head node
            ValidationException: If parameters invalid
        """
        pass

    def get_job(self, job_id: str) -> Job:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass

    def list_jobs(
        self,
        status_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Job]:
        """
        List jobs.
        
        Args:
            status_filter: Filter by status
            limit: Maximum number to return
            
        Returns:
            List of Job instances
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def cancel_job(self, job_id: str):
        """
        Cancel a job.
        
        Args:
            job_id: Job ID
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass

    def get_job_logs(
        self,
        job_id: str,
        lines: Optional[int] = None,
        stderr: bool = False
    ) -> str:
        """
        Get job logs.
        
        Args:
            job_id: Job ID
            lines: Number of lines from end
            stderr: If True, get stderr
            
        Returns:
            Log contents
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass

    def stream_job_logs(
        self,
        job_id: str,
        stderr: bool = False
    ) -> Iterator[str]:
        """
        Stream job logs in real-time.
        
        Args:
            job_id: Job ID
            stderr: If True, stream stderr
            
        Yields:
            Log lines as they arrive
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass

    def list_nodes(self) -> List[Node]:
        """
        List all nodes.
        
        Returns:
            List of Node instances
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def get_node(self, node_name: str) -> Node:
        """
        Get node by name.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance
            
        Raises:
            NodeNotFoundException: If node not found
            ConnectionException: If cannot connect
        """
        pass

    def register_node(
        self,
        node_name: str,
        address: str,
        num_gpus: int
    ) -> dict:
        """
        Register a worker node (worker use only).
        
        Args:
            node_name: Node name
            address: Node address
            num_gpus: Number of GPUs
            
        Returns:
            Registration response
            
        Raises:
            ValidationException: If parameters invalid
            ConnectionException: If cannot connect
        """
        pass

    def send_heartbeat(
        self,
        node_name: str,
        gpu_stats: List[GPUStats]
    ):
        """
        Send heartbeat (worker use only).
        
        Args:
            node_name: Node name
            gpu_stats: GPU statistics
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def poll_for_job(self, node_name: str, timeout: int = 30) -> Optional[Job]:
        """
        Long-poll for job assignment (worker use only).
        
        Args:
            node_name: Node name
            timeout: Poll timeout in seconds
            
        Returns:
            Job if assigned, None if timeout
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def report_job_complete(self, job_id: str, exit_code: int):
        """
        Report job completion (worker use only).
        
        Args:
            job_id: Job ID
            exit_code: Process exit code
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def report_job_failed(self, job_id: str, error_message: str):
        """
        Report job failure (worker use only).
        
        Args:
            job_id: Job ID
            error_message: Error message
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass

    def health_check(self) -> bool:
        """
        Check if head node is healthy.
        
        Returns:
            True if healthy
        """
        pass
