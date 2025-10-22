from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

from scheduler.core.exceptions import InvalidRequirementException


class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeStatus(Enum):
    """Node status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"


class GPUStats:
    """GPU statistics snapshot"""

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        temperature: int,
        power_draw: int,
        power_limit: int
    ):
        """
        Initialize GPU statistics.
        
        Args:
            gpu_id: GPU index (0-based)
            utilization: GPU utilization percentage (0-100)
            memory_used: Used GPU memory in bytes
            memory_total: Total GPU memory in bytes
            temperature: GPU temperature in Celsius
            power_draw: Current power draw in watts
            power_limit: Power limit in watts
        """
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all GPU stats
        """
        pass

    @classmethod
    def from_dict(cls, data: dict) -> 'GPUStats':
        """Create GPUStats from dictionary.
        
        Args:
            data: Dictionary containing GPU stats
            
        Returns:
            GPUStats instance
        """
        pass

    def is_free(self, util_threshold: float, mem_threshold: float) -> bool:
        """Check if GPU is considered free based on thresholds.
        
        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage
            
        Returns:
            True if GPU is below both thresholds
        """
        pass


class GPU:
    """GPU resource representation"""

    def __init__(
        self,
        gpu_id: int,
        stats: GPUStats,
        assigned_job_id: Optional[str] = None,
        stable_since: Optional[datetime] = None
    ):
        """
        Initialize GPU.
        
        Args:
            gpu_id: GPU index
            stats: Current GPU statistics
            assigned_job_id: Job ID if GPU is assigned, None if free
            stable_since: Timestamp when GPU became stable (below threshold)
        """
        pass

    def update_stats(self, stats: GPUStats, util_threshold: float, mem_threshold: float):
        """Update GPU statistics and stability tracking.
        
        Args:
            stats: New GPU statistics
            util_threshold: Utilization threshold for stability
            mem_threshold: Memory threshold for stability
        """
        pass

    def is_stable(self, stable_time: int) -> bool:
        """Check if GPU has been stable for required duration.
        
        Args:
            stable_time: Required stable time in seconds
            
        Returns:
            True if GPU has been below threshold for stable_time seconds
        """
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing GPU data
        """
        pass

    @classmethod
    def from_dict(cls, data: dict) -> 'GPU':
        """Create GPU from dictionary.
        
        Args:
            data: Dictionary containing GPU data
            
        Returns:
            GPU instance
        """
        pass


class JobRequirement:
    """Job resource requirement specification"""

    def __init__(self, requirement_str: str):
        """
        Parse and initialize job requirement.
        
        Args:
            requirement_str: Requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")
            
        Raises:
            InvalidRequirementException: If requirement string is invalid
        """
        pass

    @property
    def alternatives(self) -> List[Tuple[Optional[str], int]]:
        """Get list of alternative requirements.
        
        Returns:
            List of (node_name, num_gpus) tuples. node_name is None for any node.
        """
        pass

    def matches_node(self, node_name: str, available_gpus: int) -> bool:
        """Check if a node satisfies this requirement.
        
        Args:
            node_name: Name of the node to check
            available_gpus: Number of available GPUs on the node
            
        Returns:
            True if node satisfies any alternative in the requirement
        """
        pass

    def __str__(self) -> str:
        """String representation of requirement.
        
        Returns:
            Human-readable requirement string
        """
        pass


class Job:
    """Job representation"""

    def __init__(
        self,
        job_id: str,
        name: str,
        script: str,
        requirements: JobRequirement,
        script_args: List[str] = None,
        working_dir: str = None,
        env_vars: Dict[str, str] = None,
        dependencies: List[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None,
        submitted_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        status: JobStatus = JobStatus.PENDING,
        assigned_node: Optional[str] = None,
        assigned_gpus: Optional[List[int]] = None,
        exit_code: Optional[int] = None,
        error_message: Optional[str] = None,
        versioned_script_path: Optional[str] = None
    ):
        """
        Initialize job.
        
        Args:
            job_id: Unique job identifier
            name: Human-readable job name
            script: Path to script to execute
            requirements: JobRequirement instance
            script_args: Arguments to pass to script
            working_dir: Working directory for execution
            env_vars: Environment variables
            dependencies: List of job IDs this job depends on
            priority: Job priority (higher = more important)
            timeout: Job timeout in seconds
            submitted_at: Submission timestamp
            started_at: Start timestamp
            completed_at: Completion timestamp
            status: Current job status
            assigned_node: Node name where job is assigned/running
            assigned_gpus: List of GPU IDs assigned to job
            exit_code: Process exit code
            error_message: Error message if failed
            versioned_script_path: Path to versioned script copy
        """
        pass

    def get_runtime(self) -> Optional[timedelta]:
        """Get job runtime duration.
        
        Returns:
            Runtime as timedelta if job started, None otherwise
        """
        pass

    def can_start(self, completed_job_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied.
        
        Args:
            completed_job_ids: Set of completed job IDs
            
        Returns:
            True if all dependencies are completed
        """
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all job data
        """
        pass

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create Job from dictionary.
        
        Args:
            data: Dictionary containing job data
            
        Returns:
            Job instance
        """
        pass


class Node:
    """Worker node representation"""

    def __init__(
        self,
        node_name: str,
        address: str,
        num_gpus: int,
        gpus: List[GPU] = None,
        status: NodeStatus = NodeStatus.INITIALIZING,
        last_heartbeat: Optional[datetime] = None,
        registered_at: Optional[datetime] = None,
        grace_period_until: Optional[datetime] = None
    ):
        """
        Initialize node.
        
        Args:
            node_name: Unique node identifier
            address: Node IP address or hostname
            num_gpus: Number of GPUs on this node
            gpus: List of GPU instances
            status: Current node status
            last_heartbeat: Last heartbeat timestamp
            registered_at: Registration timestamp
            grace_period_until: Timestamp until which node is in grace period
        """
        pass

    def update_heartbeat(self, gpu_stats: List[GPUStats]):
        """Update node heartbeat and GPU statistics.
        
        Args:
            gpu_stats: List of GPU statistics from heartbeat
        """
        pass

    def get_free_gpus(self, util_threshold: float, mem_threshold: float, stable_time: int) -> List[int]:
        """Get list of free and stable GPU IDs.
        
        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage
            stable_time: Required stable time in seconds
            
        Returns:
            List of GPU IDs that are free and stable
        """
        pass

    def is_in_grace_period(self) -> bool:
        """Check if node is currently in grace period.
        
        Returns:
            True if in grace period
        """
        pass

    def start_grace_period(self, duration: int):
        """Start a grace period for this node.
        
        Args:
            duration: Grace period duration in seconds
        """
        pass

    def assign_gpus(self, gpu_ids: List[int], job_id: str):
        """Assign GPUs to a job.
        
        Args:
            gpu_ids: List of GPU IDs to assign
            job_id: Job ID to assign GPUs to
        """
        pass

    def release_gpus(self, gpu_ids: List[int]):
        """Release GPUs from a job.
        
        Args:
            gpu_ids: List of GPU IDs to release
        """
        pass

    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all node data
        """
        pass

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        """Create Node from dictionary.
        
        Args:
            data: Dictionary containing node data
            
        Returns:
            Node instance
        """
        pass

