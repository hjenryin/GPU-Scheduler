from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
import logging

from scheduler.core.exceptions import InvalidRequirementException

logger = logging.getLogger(__name__)


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
    
    # Class attributes with defaults (enables create_autospec to work with spec_set)
    gpu_id: int = 0
    utilization: float = 0.0
    memory_used: int = 0
    memory_total: int = 0
    temperature: int = 0
    power_draw: int = 0
    power_limit: int = 0
    running_job_id: Optional[str] = None

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        temperature: int,
        power_draw: int,
        power_limit: int,
        running_job_id: Optional[str] = None
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
        self.gpu_id = gpu_id
        self.utilization = utilization
        self.memory_used = memory_used
        self.memory_total = memory_total
        self.temperature = temperature
        self.power_draw = power_draw
        self.power_limit = power_limit
        self.running_job_id = running_job_id

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all GPU stats
        """
        return {
            'gpu_id': self.gpu_id,
            'utilization': self.utilization,
            'memory_used': self.memory_used,
            'memory_total': self.memory_total,
            'temperature': self.temperature,
            'power_draw': self.power_draw,
            'power_limit': self.power_limit,
            'running_job_id': self.running_job_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GPUStats':
        """Create GPUStats from dictionary.

        Args:
            data: Dictionary containing GPU stats

        Returns:
            GPUStats instance
        """
        return cls(
            gpu_id=data['gpu_id'],
            utilization=data['utilization'],
            memory_used=data['memory_used'],
            memory_total=data['memory_total'],
            temperature=data['temperature'],
            power_draw=data['power_draw'],
            power_limit=data['power_limit'],
            running_job_id=data.get('running_job_id')
        )

    def is_free(self, util_threshold: float, mem_threshold: float) -> bool:
        """Check if GPU is considered free based on thresholds.

        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage

        Returns:
            True if GPU is below both thresholds
        """
        memory_percent = (self.memory_used / self.memory_total * 100) if self.memory_total > 0 else 0
        return self.utilization < util_threshold and memory_percent < mem_threshold


class GPU:
    """GPU resource representation"""
    
    # Class attributes with defaults (enables create_autospec to work with spec_set)
    gpu_id: int = 0
    stats: GPUStats = None
    stable_since: Optional[datetime] = None

    def __init__(
        self,
        gpu_id: int,
        stats: GPUStats,
        stable_since: Optional[datetime] = None
    ):
        """
        Initialize GPU.

        Args:
            gpu_id: GPU index
            stats: Current GPU statistics
            stable_since: Timestamp when GPU became stable (below threshold)
        """
        self.gpu_id = gpu_id
        self.stats = stats
        self.stable_since = stable_since

    def update_stats(self, stats: GPUStats, util_threshold: float, mem_threshold: float):
        """Update GPU statistics and stability tracking.

        Args:
            stats: New GPU statistics
            util_threshold: Utilization threshold for stability
            mem_threshold: Memory threshold for stability
        """
        self.stats = stats

        # Check if GPU is currently free (below thresholds)
        # Note: We rely purely on actual usage monitoring, not internal job tracking
        # This allows the scheduler to work in shared GPU environments
        is_free = stats.is_free(util_threshold, mem_threshold)
        
        if is_free:
            # If it was already stable, keep the timestamp
            if self.stable_since is None:
                self.stable_since = datetime.now()
                logger.debug(f"GPU {self.gpu_id}: Set stable_since to {self.stable_since}")
        else:
            # GPU is not free, reset stability
            self.stable_since = None
            logger.debug(f"GPU {self.gpu_id}: Reset stable_since (GPU not free)")

    def is_stable(self, stable_time: int) -> bool:
        """Check if GPU has been stable for required duration.

        Args:
            stable_time: Required stable time in seconds

        Returns:
            True if GPU has been below threshold for stable_time seconds
        """
        if self.stable_since is None:
            return False

        current_time = datetime.now()
        elapsed = (current_time - self.stable_since).total_seconds()
        is_stable = elapsed >= stable_time
        logger.debug(f"GPU {self.gpu_id}: is_stable={is_stable} (elapsed={elapsed:.2f}s, required={stable_time}s)")
        return is_stable

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing GPU data
        """
        return {
            'gpu_id': self.gpu_id,
            'stats': self.stats.to_dict(),
            'stable_since': self.stable_since.isoformat() if self.stable_since else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GPU':
        """Create GPU from dictionary.

        Args:
            data: Dictionary containing GPU data

        Returns:
            GPU instance
        """
        stable_since = None
        if data.get('stable_since'):
            stable_since = datetime.fromisoformat(data['stable_since'])

        return cls(
            gpu_id=data['gpu_id'],
            stats=GPUStats.from_dict(data['stats']),
            stable_since=stable_since
        )


class JobRequirement:
    """Job resource requirement specification"""
    
    # Class attribute with default (enables create_autospec to work with spec_set)
    _alternatives: List[Tuple[Optional[str], int]] = []

    def __init__(self, requirement_str: str):
        """
        Parse and initialize job requirement.

        Args:
            requirement_str: Requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")

        Raises:
            InvalidRequirementException: If requirement string is invalid
        """
        self._alternatives = self._parse_requirements(requirement_str)

    def _parse_requirements(self, req_str: str) -> List[Tuple[Optional[str], int]]:
        """Parse requirement string into list of alternatives."""
        if not req_str or not req_str.strip():
            raise InvalidRequirementException("Requirement string cannot be empty")

        alternatives = []
        # Split by comma for alternatives (e.g., "gpu1:2,gpu2:4")
        parts = req_str.split(',')

        for part in parts:
            part = part.strip()
            if ':' in part:
                # Node-specific requirement (e.g., "gpu1:4")
                node_gpu = part.split(':', 1)
                if len(node_gpu) != 2:
                    raise InvalidRequirementException(f"Invalid requirement format: {part}")
                node_name = node_gpu[0].strip()
                try:
                    num_gpus = int(node_gpu[1].strip())
                except ValueError:
                    raise InvalidRequirementException(f"Invalid GPU count: {node_gpu[1]}")
                if num_gpus <= 0:
                    raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
                alternatives.append((node_name, num_gpus))
            else:
                # Any node requirement (e.g., "2")
                try:
                    num_gpus = int(part)
                except ValueError:
                    raise InvalidRequirementException(f"Invalid GPU count: {part}")
                if num_gpus <= 0:
                    raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
                alternatives.append((None, num_gpus))

        return alternatives

    @property
    def alternatives(self) -> List[Tuple[Optional[str], int]]:
        """Get list of alternative requirements.

        Returns:
            List of (node_name, num_gpus) tuples. node_name is None for any node.
        """
        return self._alternatives

    def serialize(self) -> str:
        """Serialize to requirement string for JSON/API transmission.

        Returns:
            Machine-readable requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")
        """
        parts = []
        for node_name, num_gpus in self._alternatives:
            if node_name is None:
                parts.append(str(num_gpus))
            else:
                parts.append(f"{node_name}:{num_gpus}")
        return ",".join(parts)

    def __str__(self) -> str:
        """String representation of requirement for human display.

        Returns:
            Human-readable requirement string (e.g., "2 GPUs on any node")
        """
        parts = []
        for node_name, num_gpus in self._alternatives:
            if node_name is None:
                parts.append(f"{num_gpus} GPUs on any node")
            else:
                parts.append(f"{num_gpus} GPUs on {node_name}")
        return " OR ".join(parts)


class Job:
    """Job representation"""
    
    # Class attributes with defaults (enables create_autospec to work with spec_set)
    job_id: str = None
    name: str = None
    script: str = None
    requirements: JobRequirement = None
    script_args: List[str] = None
    working_dir: Optional[str] = None
    env_vars: Dict[str, str] = None
    dependencies: List[str] = None
    priority: int = 0
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: JobStatus = JobStatus.PENDING
    assigned_node: Optional[str] = None
    assigned_gpus: Optional[List[int]] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    versioned_script_path: Optional[str] = None

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
        self.job_id = job_id
        self.name = name
        self.script = script
        self.requirements = requirements
        self.script_args = script_args or []
        self.working_dir = working_dir
        self.env_vars = env_vars or {}
        self.dependencies = dependencies or []
        self.priority = priority
        self.submitted_at = submitted_at or datetime.now()
        self.started_at = started_at
        self.completed_at = completed_at
        self.status = status
        self.assigned_node = assigned_node
        self.assigned_gpus = assigned_gpus
        self.exit_code = exit_code
        self.error_message = error_message
        self.versioned_script_path = versioned_script_path

    @property
    def start_time(self) -> Optional[datetime]:
        """Get job start time (alias for started_at)."""
        return self.started_at

    @property
    def end_time(self) -> Optional[datetime]:
        """Get job end time (alias for completed_at)."""
        return self.completed_at

    def get_runtime(self) -> Optional[timedelta]:
        """Get job runtime duration.

        Returns:
            Runtime as timedelta if job started, None otherwise
        """
        if self.started_at is None:
            return None

        end_time = self.completed_at if self.completed_at else datetime.now()
        return end_time - self.started_at

    def can_start(self, completed_job_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied.

        Args:
            completed_job_ids: Set of completed job IDs

        Returns:
            True if all dependencies are completed
        """
        if not self.dependencies:
            return True

        return all(dep_id in completed_job_ids for dep_id in self.dependencies)

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all job data
        """
        return {
            'job_id': self.job_id,
            'name': self.name,
            'script': self.script,
            'requirements': self.requirements.serialize(),
            'script_args': self.script_args,
            'working_dir': self.working_dir,
            'env_vars': self.env_vars,
            'dependencies': self.dependencies,
            'priority': self.priority,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status.value,
            'assigned_node': self.assigned_node,
            'assigned_gpus': self.assigned_gpus,
            'exit_code': self.exit_code,
            'error_message': self.error_message,
            'versioned_script_path': self.versioned_script_path
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create Job from dictionary.

        Args:
            data: Dictionary containing job data

        Returns:
            Job instance
        """
        # Parse timestamps
        submitted_at = datetime.fromisoformat(data['submitted_at']) if data.get('submitted_at') else None
        started_at = datetime.fromisoformat(data['started_at']) if data.get('started_at') else None
        completed_at = datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None

        # Parse status
        status = JobStatus(data['status']) if data.get('status') else JobStatus.PENDING

        # Parse requirements
        requirements = JobRequirement(data['requirements'])

        return cls(
            job_id=data['job_id'],
            name=data['name'],
            script=data['script'],
            requirements=requirements,
            script_args=data.get('script_args'),
            working_dir=data.get('working_dir'),
            env_vars=data.get('env_vars'),
            dependencies=data.get('dependencies'),
            priority=data.get('priority', 0),
            submitted_at=submitted_at,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            assigned_node=data.get('assigned_node'),
            assigned_gpus=data.get('assigned_gpus'),
            exit_code=data.get('exit_code'),
            error_message=data.get('error_message'),
            versioned_script_path=data.get('versioned_script_path')
        )


class Node:
    """Worker node representation"""
    
    # Class attributes with defaults (enables create_autospec to work with spec_set)
    node_name: str = None
    address: str = None
    num_gpus: int = 0
    gpus: List[GPU] = None
    status: NodeStatus = NodeStatus.INITIALIZING
    last_heartbeat: Optional[datetime] = None
    registered_at: Optional[datetime] = None
    grace_period_until: Optional[datetime] = None

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
        self.node_name = node_name
        self.address = address
        self.num_gpus = num_gpus
        self.gpus = gpus if gpus is not None else []
        self.status = status
        self.last_heartbeat = last_heartbeat
        self.registered_at = registered_at or datetime.now()
        self.grace_period_until = grace_period_until

    def update_heartbeat(self, gpu_stats: List[GPUStats]):
        """Update node heartbeat and GPU statistics.

        Args:
            gpu_stats: List of GPU statistics from heartbeat
        """
        self.last_heartbeat = datetime.now()
        self.status = NodeStatus.CONNECTED

        # Update GPU statistics
        # Note: This assumes gpu_stats are in order by GPU ID
        for stats in gpu_stats:
            gpu_id = stats.gpu_id
            # Find or create GPU object
            if gpu_id < len(self.gpus):
                # Update existing GPU - thresholds will be passed by caller
                # For now, just update the stats directly
                self.gpus[gpu_id].stats = stats
            # Note: GPU stability tracking happens in GPU.update_stats which
            # should be called separately with proper thresholds

    def get_free_gpus(self, util_threshold: float, mem_threshold: float, stable_time: int) -> List[int]:
        """Get list of free and stable GPU IDs.

        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage
            stable_time: Required stable time in seconds

        Returns:
            List of GPU IDs that are free and stable (based on actual usage)
        """
        free_gpus = []
        for gpu in self.gpus:
            # Check if GPU has low usage and is stable
            # We rely purely on actual GPU monitoring, not internal job tracking
            is_free = gpu.stats.is_free(util_threshold, mem_threshold)
            is_stable = gpu.is_stable(stable_time)
            memory_percent = (gpu.stats.memory_used / gpu.stats.memory_total * 100) if gpu.stats.memory_total > 0 else 0
            logger.debug(f"GPU {gpu.gpu_id}: util={gpu.stats.utilization}%, mem={memory_percent:.1f}%, is_free={is_free}, is_stable={is_stable}, stable_since={gpu.stable_since}")
            if is_free and is_stable:
                free_gpus.append(gpu.gpu_id)
        logger.debug(f"Node {self.node_name}: free GPUs = {free_gpus}")
        return free_gpus

    def is_in_grace_period(self) -> bool:
        """Check if node is currently in grace period.

        Returns:
            True if in grace period
        """
        if self.grace_period_until is None:
            return False
        return datetime.now() < self.grace_period_until

    def start_grace_period(self, duration: int):
        """Start a grace period for this node.

        Args:
            duration: Grace period duration in seconds
        """
        self.grace_period_until = datetime.now() + timedelta(seconds=duration)

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing all node data
        """
        return {
            'node_name': self.node_name,
            'address': self.address,
            'num_gpus': self.num_gpus,
            'gpus': [gpu.to_dict() for gpu in self.gpus],
            'status': self.status.value,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'grace_period_until': self.grace_period_until.isoformat() if self.grace_period_until else None
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        """Create Node from dictionary.

        Args:
            data: Dictionary containing node data

        Returns:
            Node instance
        """
        # Parse timestamps
        last_heartbeat = datetime.fromisoformat(data['last_heartbeat']) if data.get('last_heartbeat') else None
        registered_at = datetime.fromisoformat(data['registered_at']) if data.get('registered_at') else None
        grace_period_until = datetime.fromisoformat(data['grace_period_until']) if data.get('grace_period_until') else None

        # Parse status
        status = NodeStatus(data['status']) if data.get('status') else NodeStatus.INITIALIZING

        # Parse GPUs
        gpus = [GPU.from_dict(gpu_data) for gpu_data in data.get('gpus', [])]

        return cls(
            node_name=data['node_name'],
            address=data['address'],
            num_gpus=data['num_gpus'],
            gpus=gpus,
            status=status,
            last_heartbeat=last_heartbeat,
            registered_at=registered_at,
            grace_period_until=grace_period_until
        )

