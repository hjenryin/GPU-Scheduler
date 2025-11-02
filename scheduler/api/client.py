import logging
import time
from datetime import datetime
from typing import Iterator, List, Optional, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scheduler.core import (
    ConnectionException,
    JobNotFoundException,
    NodeNotFoundException,
    ValidationException,
)
from scheduler.core import GPU, Job, JobStatus, Node, NodeStatus, GPUStats
from scheduler.core import Config, load_config
from scheduler.core import constants
from scheduler.core import parse_address

logger = logging.getLogger(__name__)


class SchedulerClient:
    """HTTP client for scheduler API"""

    def __init__(self, address: Optional[str] = None, config: Optional[Config] = None):
        """
        Initialize scheduler client.

        Args:
            address: Head node address (host:port). Auto-detect if None.
            config: Configuration instance (load default if None)
        """
        if config is None:
            config = load_config()

        self.config = config

        # Determine head node address
        # Priority: explicit address > recorded address > config.address > default
        if address:
            self.head_address = address
            self._head_address_source = "explicit"
            self._has_recorded_address = False  # Explicit means not from worker
        else:
            # Try to load recorded head address
            from scheduler.core import load_head_info
            recorded_address = load_head_info()
            
            if recorded_address:
                self.head_address = recorded_address
                self._head_address_source = "recorded"
                self._has_recorded_address = True
            elif config.address:
                self.head_address = config.address
                self._head_address_source = "config"
                self._has_recorded_address = False
            else:
                # Default to localhost with configured port
                self.head_address = f"localhost:{config.head.port}"
                self._head_address_source = "default"
                self._has_recorded_address = False

        # Parse and validate address
        host, port = parse_address(self.head_address)
        self.base_url = f"http://{host}:{port}{constants.API_BASE_PATH}"

        # Create session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.debug(f"Initialized SchedulerClient with base URL: {self.base_url}")
    
    def _format_connection_error(self, operation: str, original_error) -> str:
        """
        Format a helpful connection error message.
        
        Args:
            operation: What operation failed (e.g., "submit job", "list jobs")
            original_error: The original exception
        
        Returns:
            Formatted error message
        """
        error_msg = f"Failed to {operation}"
        
        # Check if no worker is connected
        if hasattr(self, '_has_recorded_address') and not self._has_recorded_address:
            if self._head_address_source == "default":
                error_msg += (
                    f"\n\n❌ No worker is connected to a scheduler cluster."
                    f"\n\nTo fix this:"
                    f"\n  1. Start a head node: scheduler start --head"
                    f"\n  2. Or connect to an existing head: scheduler start --address=hostname:port"
                    f"\n\nExample: scheduler start --address=turing1:8266"
                    f"\n\nOriginal error: {original_error}"
                )
                return error_msg
        
        error_msg += f" at {self.head_address}"
        
        # Add context based on how we got the address
        if hasattr(self, '_head_address_source'):
            if self._head_address_source == "recorded":
                error_msg += (
                    f"\n\nThe head node may have stopped or is unreachable."
                    f"\nTry reconnecting: scheduler start --address=hostname:port"
                )
            elif self._head_address_source == "config":
                error_msg += (
                    f"\n\nCannot reach head node at the configured address."
                    f"\nCheck if the head node is running at: {self.head_address}"
                )
        
        error_msg += f"\n\nOriginal error: {original_error}"
        return error_msg

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
        Submit a job.

        This method:
        1. Generates job_id on the client
        2. Creates git snapshot locally (if in a git repository)
        3. Sends job with snapshot info to head node

        Args:
            (same as JobManager.submit_job)

        Returns:
            Created Job instance

        Raises:
            ConnectionException: If cannot connect to head node
            ValidationException: If parameters invalid
        """
        from scheduler.core import generate_job_id
        from scheduler.worker import GitSnapshotManager
        import os

        # Generate job_id on client
        job_id = generate_job_id()

        # Use current working directory if not specified
        if working_dir is None:
            working_dir = os.getcwd()

        # Create git snapshot on client machine
        snapshot_ref = None
        snapshot_working_dir = None

        try:
            git_manager = GitSnapshotManager(self.config)
            if git_manager.is_git_repository(working_dir):
                logger.info(f"Creating git snapshot for job {job_id} on client")
                snapshot_result = git_manager.create_snapshot(job_id, working_dir)
                if snapshot_result:
                    snapshot_ref, snapshot_working_dir = snapshot_result
                    logger.info(f"Created snapshot {snapshot_ref} at {snapshot_working_dir}")
                else:
                    logger.debug(f"No snapshot created for job {job_id}")
        except Exception as e:
            # Don't fail job submission if snapshot creation fails
            logger.warning(f"Failed to create snapshot for job {job_id}: {e}")

        payload = {
            "job_id": job_id,
            "script": script,
            "requirements": requirements,
            "name": name,
            "script_args": script_args,
            "working_dir": working_dir,
            "env_vars": env_vars,
            "dependencies": dependencies,
            "priority": priority,
            "snapshot_ref": snapshot_ref,
            "snapshot_working_dir": snapshot_working_dir,
        }

        try:
            response = self.session.post(f"{self.base_url}/jobs", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return self._job_from_response(data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to submit job: {e}")
            raise ConnectionException(self._format_connection_error("submit job", e))
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid response format: {e}")
            raise ValidationException(f"Invalid response from server: {e}")

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
        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}", timeout=30)
            if response.status_code == 404:
                raise JobNotFoundException(f"Job {job_id} not found")
            response.raise_for_status()
            data = response.json()
            return self._job_from_response(data)
        except JobNotFoundException:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            raise ConnectionException(self._format_connection_error(f"get job {job_id}", e))

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
        params = {}
        if status_filter:
            params["status"] = status_filter
        if limit:
            params["limit"] = limit

        try:
            response = self.session.get(f"{self.base_url}/jobs", params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return [self._job_from_response(job_data) for job_data in data.get("jobs", [])]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list jobs: {e}")
            raise ConnectionException(self._format_connection_error("list jobs", e))

    def cancel_job(self, job_id: str):
        """
        Cancel a job.

        Args:
            job_id: Job ID

        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        try:
            # Fixed: Use DELETE method to /jobs/{job_id} (not POST to /cancel)
            response = self.session.delete(f"{self.base_url}/jobs/{job_id}", timeout=30)
            if response.status_code == 404:
                raise JobNotFoundException(f"Job {job_id} not found")
            response.raise_for_status()
        except JobNotFoundException:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

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
        params = {}
        if lines:
            params["lines"] = lines
        if stderr:
            params["stderr"] = "true"

        try:
            response = self.session.get(f"{self.base_url}/jobs/{job_id}/logs", params=params, timeout=30)
            if response.status_code == 404:
                raise JobNotFoundException(f"Job {job_id} not found")
            response.raise_for_status()
            return response.text
        except JobNotFoundException:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get logs for job {job_id}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

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
        params = {"stream": "true"}
        if stderr:
            params["stderr"] = "true"

        try:
            response = self.session.get(
                f"{self.base_url}/jobs/{job_id}/logs",
                params=params,
                stream=True,
                timeout=None  # No timeout for streaming
            )
            if response.status_code == 404:
                raise JobNotFoundException(f"Job {job_id} not found")
            response.raise_for_status()

            for line in response.iter_lines(decode_unicode=True):
                if line:
                    yield line
        except JobNotFoundException:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to stream logs for job {job_id}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

    def list_nodes(self) -> List[Node]:
        """
        List all nodes.

        Returns:
            List of Node instances

        Raises:
            ConnectionException: If cannot connect
        """
        try:
            response = self.session.get(f"{self.base_url}/nodes", timeout=30)
            response.raise_for_status()
            data = response.json()
            # API returns a list directly, not a dict with "nodes" key
            return [self._node_from_response(node_data) for node_data in data]
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to list nodes: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

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
        try:
            response = self.session.get(f"{self.base_url}/nodes/{node_name}", timeout=30)
            if response.status_code == 404:
                raise NodeNotFoundException(f"Node {node_name} not found")
            response.raise_for_status()
            data = response.json()
            return self._node_from_response(data)
        except NodeNotFoundException:
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get node {node_name}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

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
        payload = {
            "node_name": node_name,
            "address": address,
            "num_gpus": num_gpus
        }

        try:
            response = self.session.post(f"{self.base_url}/nodes/register", json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to register node {node_name}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

    def send_heartbeat(
        self,
        node_name: str,
        gpu_stats: List[GPUStats],
        log_chunks: List = None
    ):
        """
        Send heartbeat with log chunks (worker use only).

        Args:
            node_name: Node name
            gpu_stats: GPU statistics
            log_chunks: List of LogChunk objects to send

        Returns:
            HeartbeatResponse with shutdown_requested and log_requests

        Raises:
            ConnectionException: If cannot connect
        """
        from scheduler.api.schemas import HeartbeatResponse

        payload = {
            "gpu_stats": [stats.to_dict() for stats in gpu_stats],
            "log_chunks": [chunk.dict() for chunk in (log_chunks or [])]
        }

        try:
            response = self.session.post(f"{self.base_url}/nodes/{node_name}/heartbeat", json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            return HeartbeatResponse(**data)
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send heartbeat for node {node_name}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

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
        params = {"timeout": timeout}

        try:
            # Fixed: Use /workers/{node_name}/jobs/next (not /poll)
            response = self.session.get(
                f"{self.base_url}/workers/{node_name}/jobs/next",
                params=params,
                timeout=timeout + 5  # Add buffer to request timeout
            )
            response.raise_for_status()

            if response.status_code == 204:  # No content - no job available
                return None

            data = response.json()
            return self._job_from_response(data) if data else None
        except requests.exceptions.Timeout:
            # Timeout is expected for long-polling
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to poll for job on node {node_name}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

    def report_job_complete(self, job_id: str, exit_code: int):
        """
        Report job completion (worker use only).

        Args:
            job_id: Job ID
            exit_code: Process exit code

        Raises:
            ConnectionException: If cannot connect
        """
        # Fixed: Send exit_code as query parameter (not JSON body)
        try:
            response = self.session.post(
                f"{self.base_url}/workers/jobs/{job_id}/complete",
                params={"exit_code": exit_code},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to report completion for job {job_id}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

    def report_job_failed(self, job_id: str, error_message: str):
        """
        Report job failure (worker use only).

        Args:
            job_id: Job ID
            error_message: Error message

        Raises:
            ConnectionException: If cannot connect
        """
        # Fixed: Send error_message as query parameter (not JSON body)
        try:
            response = self.session.post(
                f"{self.base_url}/workers/jobs/{job_id}/fail",
                params={"error_message": error_message},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to report failure for job {job_id}: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")

    def health_check(self) -> bool:
        """
        Check if head node is healthy.

        Returns:
            True if healthy
        """
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False

    def _job_from_response(self, data: dict) -> Job:
        """
        Convert API response to Job object.

        Args:
            data: Job response data

        Returns:
            Job instance
        """
        from scheduler.core import JobRequirement

        # Parse timestamps
        submitted_at = datetime.fromisoformat(data["submitted_at"]) if data.get("submitted_at") else None
        started_at = datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None
        completed_at = datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None

        # Parse status
        status = JobStatus(data["status"])

        # Parse requirements
        requirements = JobRequirement(data["requirements"])

        return Job(
            job_id=data["job_id"],
            name=data["name"],
            script=data["script"],
            requirements=requirements,
            status=status,
            submitted_at=submitted_at,
            started_at=started_at,
            completed_at=completed_at,
            assigned_node=data.get("assigned_node"),
            assigned_gpus=data.get("assigned_gpus"),
            exit_code=data.get("exit_code"),
            error_message=data.get("error_message"),
            script_args=data.get("script_args"),
            working_dir=data.get("working_dir"),
            env_vars=data.get("env_vars"),
            dependencies=data.get("dependencies"),
            priority=data.get("priority", 0),
            snapshot_ref=data.get("snapshot_ref"),
            snapshot_working_dir=data.get("snapshot_working_dir"),
        )

    def _node_from_response(self, data: dict) -> Node:
        """
        Convert API response to Node object.

        Args:
            data: Node response data

        Returns:
            Node instance
        """
        # Parse timestamps
        registered_at = (
            datetime.fromisoformat(data["registered_at"])
            if data.get("registered_at")
            else None
        )
        last_heartbeat = (
            datetime.fromisoformat(data["last_heartbeat"])
            if data.get("last_heartbeat")
            else None
        )

        # Parse status
        status = (
            NodeStatus(data["status"])
            if data.get("status")
            else NodeStatus.INITIALIZING
        )

        # Create node
        node = Node(
            node_name=data["node_name"],
            address=data["address"],
            num_gpus=data["num_gpus"],
            status=status,
            last_heartbeat=last_heartbeat,
            registered_at=registered_at
        )

        # Parse GPUs if present
        if data.get("gpus"):
            node.gpus = []
            for gpu_data in data["gpus"]:
                stats = GPUStats(
                    gpu_id=gpu_data["gpu_id"],
                    utilization=gpu_data["utilization"],
                    memory_used=gpu_data["memory_used"],
                    memory_total=gpu_data["memory_total"],
                    temperature=gpu_data["temperature"],
                    power_draw=gpu_data["power_draw"],
                    power_limit=gpu_data.get("power_limit")
                )

                stable_since = datetime.fromisoformat(gpu_data["stable_since"]) if gpu_data.get("stable_since") else None

                gpu = GPU(
                    gpu_id=gpu_data["gpu_id"],
                    stats=stats,
                    stable_since=stable_since
                )
                node.gpus.append(gpu)

        return node

    def shutdown_cluster(self, graceful_timeout: int = 60, force: bool = False) -> bool:
        """
        Request head node to shutdown entire cluster.
        
        Args:
            graceful_timeout: Seconds to wait for graceful shutdown
            force: Whether to force kill if graceful shutdown fails
            
        Returns:
            True if shutdown request was sent successfully
            
        Raises:
            ConnectionException: If cannot connect to head node
        """
        payload = {
            "graceful_timeout": graceful_timeout,
            "force": force
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/shutdown/cluster",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "shutdown_initiated":
                logger.info(f"Cluster shutdown initiated successfully: {data}")
                return True
            else:
                logger.warning(f"Unexpected shutdown response: {data}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to request cluster shutdown: {e}")
            raise ConnectionException(f"Failed to connect to head node: {e}")
