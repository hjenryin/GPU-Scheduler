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
    UNTRACKED = "untracked"


class NodeStatus(Enum):
    """Node status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"


class ShutdownState(Enum):
    """Node shutdown state enumeration"""
    NONE = "none"              # No shutdown requested
    PENDING = "pending"        # Head has requested shutdown
    SENT = "sent"             # Head has sent signal via heartbeat response
    CONFIRMED = "confirmed"    # Worker has confirmed receipt


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
    frozen_until: Optional[datetime] = None

    def __init__(
        self,
        gpu_id: int,
        stats: GPUStats,
        stable_since: Optional[datetime] = None,
        frozen_until: Optional[datetime] = None
    ):
        """
        Initialize GPU.

        Args:
            gpu_id: GPU index
            stats: Current GPU statistics
            stable_since: Timestamp when GPU became stable (below threshold)
            frozen_until: Timestamp until which GPU is frozen (no jobs can run)
        """
        self.gpu_id = gpu_id
        self.stats = stats
        self.stable_since = stable_since
        self.frozen_until = frozen_until

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

    def is_frozen(self) -> bool:
        """Check if GPU is currently frozen.

        Returns:
            True if GPU is frozen (frozen_until is in the future)
        """
        if self.frozen_until is None:
            return False
        return datetime.now() < self.frozen_until

    def freeze(self, duration_seconds: int):
        """Freeze GPU for a specified duration.

        Args:
            duration_seconds: Duration to freeze GPU in seconds
        """
        self.frozen_until = datetime.now() + timedelta(seconds=duration_seconds)
        logger.info(f"GPU {self.gpu_id}: Frozen until {self.frozen_until}")

    def unfreeze(self):
        """Unfreeze GPU immediately."""
        self.frozen_until = None
        logger.info(f"GPU {self.gpu_id}: Unfrozen")

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing GPU data
        """
        return {
            'gpu_id': self.gpu_id,
            'stats': self.stats.to_dict(),
            'stable_since': self.stable_since.isoformat() if self.stable_since else None,
            'frozen_until': self.frozen_until.isoformat() if self.frozen_until else None
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

        frozen_until = None
        if data.get('frozen_until'):
            frozen_until = datetime.fromisoformat(data['frozen_until'])

        return cls(
            gpu_id=data['gpu_id'],
            stats=GPUStats.from_dict(data['stats']),
            stable_since=stable_since,
            frozen_until=frozen_until
        )


class JobRequirement:
    """Job resource requirement specification"""

    # Class attribute with default (enables create_autospec to work with spec_set)
    # Format: List of (node_name, min_gpus, max_gpus) where:
    # - node_name: Optional[str] - None means any node
    # - min_gpus: int - minimum GPUs required
    # - max_gpus: int - maximum GPUs to use (-1 means flexible/all available)
    _alternatives: List[Tuple[Optional[str], int, int]] = []

    def __init__(self, requirement_str: str):
        """
        Parse and initialize job requirement.

        Args:
            requirement_str: Requirement string with support for:
                - Fixed count: "2", "gpu1:4"
                - Range: "gpu1:4-8" (use 4-8 GPUs, take as many as available)
                - Flexible: "gpu1" (take all available GPUs)
                - Multiple alternatives: "gpu1:2,gpu2:4"
                - Repeated hosts: "gpu1:4,gpu1:8" (prefer more when available)

        Raises:
            InvalidRequirementException: If requirement string is invalid
        """
        self._alternatives = self._parse_requirements(requirement_str)

    def _parse_requirements(self, req_str: str) -> List[Tuple[Optional[str], int, int]]:
        """
        Parse requirement string into list of alternatives.

        Returns list of (node_name, min_gpus, max_gpus) tuples.
        max_gpus of -1 means flexible allocation (take all available GPUs on node).
        """
        if not req_str or not req_str.strip():
            raise InvalidRequirementException("Requirement string cannot be empty")

        alternatives = []
        # Split by comma for alternatives (e.g., "gpu1:2,gpu2:4")
        parts = req_str.split(',')

        for part in parts:
            part = part.strip()
            if ':' in part:
                # Node-specific requirement (e.g., "gpu1:4" or "gpu1:4-8")
                node_gpu = part.split(':', 1)
                if len(node_gpu) != 2:
                    raise InvalidRequirementException(f"Invalid requirement format: {part}")
                node_name = node_gpu[0].strip()
                gpu_spec = node_gpu[1].strip()

                # Check for range syntax (e.g., "4-8")
                if '-' in gpu_spec:
                    range_parts = gpu_spec.split('-', 1)
                    if len(range_parts) != 2:
                        raise InvalidRequirementException(f"Invalid range format: {gpu_spec}")
                    try:
                        min_gpus = int(range_parts[0].strip())
                        max_gpus = int(range_parts[1].strip())
                    except ValueError:
                        raise InvalidRequirementException(f"Invalid GPU count in range: {gpu_spec}")
                    if min_gpus <= 0:
                        raise InvalidRequirementException(f"Minimum GPU count must be positive: {min_gpus}")
                    if max_gpus <= 0:
                        raise InvalidRequirementException(f"Maximum GPU count must be positive: {max_gpus}")
                    if min_gpus > max_gpus:
                        raise InvalidRequirementException(f"Minimum GPU count cannot be greater than maximum: {min_gpus} > {max_gpus}")
                    alternatives.append((node_name, min_gpus, max_gpus))
                else:
                    # Fixed count
                    try:
                        num_gpus = int(gpu_spec)
                    except ValueError:
                        raise InvalidRequirementException(f"Invalid GPU count: {gpu_spec}")
                    if num_gpus <= 0:
                        raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
                    alternatives.append((node_name, num_gpus, num_gpus))
            else:
                # Try to parse as a number (any node with fixed count)
                try:
                    num_gpus = int(part)
                    if num_gpus <= 0:
                        raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
                    alternatives.append((None, num_gpus, num_gpus))
                except ValueError:
                    # Not a number, treat as hostname with flexible allocation
                    # e.g., "gpu1" means "take all available GPUs on gpu1"
                    node_name = part
                    if not node_name:
                        raise InvalidRequirementException(f"Invalid node name: {part}")
                    # Validate node name doesn't contain spaces (invalid format)
                    if ' ' in node_name:
                        raise InvalidRequirementException(f"Invalid requirement format: {part}. Use ':' to specify GPU count (e.g., 'gpu1:4')")
                    alternatives.append((node_name, 1, -1))  # -1 = flexible allocation

        return alternatives

    @property
    def alternatives(self) -> List[Tuple[Optional[str], int, int]]:
        """Get list of alternative requirements.

        Returns:
            List of (node_name, min_gpus, max_gpus) tuples.
            - node_name is None for any node
            - max_gpus is -1 for flexible allocation (all available)
        """
        return self._alternatives

    def serialize(self) -> str:
        """Serialize to requirement string for JSON/API transmission.

        Returns:
            Machine-readable requirement string (e.g., "2", "gpu1:4", "gpu1:4-8", "gpu1:2,gpu2:4", "gpu1")
        """
        parts = []
        for node_name, min_gpus, max_gpus in self._alternatives:
            if node_name is None:
                # Any node with fixed or range count
                if min_gpus == max_gpus:
                    parts.append(str(min_gpus))
                else:
                    parts.append(f"{min_gpus}-{max_gpus}")
            elif max_gpus == -1:
                # Flexible allocation: just the node name
                parts.append(node_name)
            elif min_gpus == max_gpus:
                # Fixed count
                parts.append(f"{node_name}:{min_gpus}")
            else:
                # Range
                parts.append(f"{node_name}:{min_gpus}-{max_gpus}")
        return ",".join(parts)

    def __str__(self) -> str:
        """String representation of requirement for human display.

        Returns:
            Human-readable requirement string
        """
        parts = []
        for node_name, min_gpus, max_gpus in self._alternatives:
            if node_name is None:
                if min_gpus == max_gpus:
                    parts.append(f"{min_gpus} GPUs on any node")
                elif max_gpus == -1:
                    parts.append(f"{min_gpus}+ GPUs on any node")
                else:
                    parts.append(f"{min_gpus}-{max_gpus} GPUs on any node")
            elif max_gpus == -1:
                parts.append(f"all available GPUs on {node_name}")
            elif min_gpus == max_gpus:
                parts.append(f"{min_gpus} GPUs on {node_name}")
            else:
                parts.append(f"{min_gpus}-{max_gpus} GPUs on {node_name}")
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
    snapshot_ref: Optional[str] = None
    snapshot_working_dir: Optional[str] = None
    after_commit_ref: Optional[str] = None
    conda_env: Optional[str] = None

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
        snapshot_ref: Optional[str] = None,
        snapshot_working_dir: Optional[str] = None,
        after_commit_ref: Optional[str] = None,
        conda_env: Optional[str] = None
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
            snapshot_ref: Git snapshot reference (commit SHA in shadow repo) - "before" commit
            snapshot_working_dir: Original working directory for snapshot
            after_commit_ref: Git commit SHA after job execution - "after" commit
            conda_env: Conda environment name for job execution
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
        self.snapshot_ref = snapshot_ref
        self.snapshot_working_dir = snapshot_working_dir
        self.after_commit_ref = after_commit_ref
        self.conda_env = conda_env

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
            'snapshot_ref': self.snapshot_ref,
            'snapshot_working_dir': self.snapshot_working_dir,
            'after_commit_ref': self.after_commit_ref,
            'conda_env': self.conda_env
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
            snapshot_ref=data.get('snapshot_ref'),
            snapshot_working_dir=data.get('snapshot_working_dir'),
            after_commit_ref=data.get('after_commit_ref'),
            conda_env=data.get('conda_env')
        )


class JobSubmitRequest:
    """Schema for job submission requests.

    This provides a type-safe interface for building job submission payloads.
    Unlike the full Job class, this only contains fields needed for submission.
    """

    def __init__(
        self,
        job_id: str,
        script: str,
        requirements: str,
        working_dir: str,
        name: Optional[str] = None,
        script_args: Optional[List[str]] = None,
        env_vars: Optional[Dict[str, str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0,
        snapshot_ref: Optional[str] = None,
        snapshot_working_dir: Optional[str] = None,
        conda_env: Optional[str] = None,
    ):
        """
        Initialize job submission request.

        Args:
            job_id: Unique job identifier
            script: Path to script to execute
            requirements: Resource requirement string (e.g., "2", "gpu1:4")
            working_dir: Working directory for execution
            name: Human-readable job name
            script_args: Arguments to pass to script
            env_vars: Environment variables
            dependencies: List of job IDs this job depends on
            priority: Job priority (higher = more important)
            snapshot_ref: Git snapshot reference
            snapshot_working_dir: Git snapshot working directory
            conda_env: Conda environment name
        """
        self.job_id = job_id
        self.script = script
        self.requirements = requirements
        self.working_dir = working_dir
        self.name = name
        self.script_args = script_args
        self.env_vars = env_vars
        self.dependencies = dependencies
        self.priority = priority
        self.snapshot_ref = snapshot_ref
        self.snapshot_working_dir = snapshot_working_dir
        self.conda_env = conda_env

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API payload."""
        return {
            "job_id": self.job_id,
            "script": self.script,
            "requirements": self.requirements,
            "working_dir": self.working_dir,
            "name": self.name,
            "script_args": self.script_args,
            "env_vars": self.env_vars,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "snapshot_ref": self.snapshot_ref,
            "snapshot_working_dir": self.snapshot_working_dir,
            "conda_env": self.conda_env,
        }


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
    shutdown_state: ShutdownState = ShutdownState.NONE

    def __init__(
        self,
        node_name: str,
        address: str,
        num_gpus: int,
        gpus: List[GPU] = None,
        status: NodeStatus = NodeStatus.INITIALIZING,
        last_heartbeat: Optional[datetime] = None,
        registered_at: Optional[datetime] = None,
        grace_period_until: Optional[datetime] = None,
        shutdown_state: ShutdownState = ShutdownState.NONE
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
            shutdown_state: Current shutdown state (NONE, PENDING, SENT, CONFIRMED)
        """
        self.node_name = node_name
        self.address = address
        self.num_gpus = num_gpus
        self.gpus = gpus if gpus is not None else []
        self.status = status
        self.last_heartbeat = last_heartbeat
        self.registered_at = registered_at or datetime.now()
        self.grace_period_until = grace_period_until
        self.shutdown_state = shutdown_state

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
            List of GPU IDs that are free, stable, and not frozen (based on actual usage)
        """
        free_gpus = []
        for gpu in self.gpus:
            # Check if GPU is frozen
            is_frozen = gpu.is_frozen()
            if is_frozen:
                logger.debug(f"GPU {gpu.gpu_id}: frozen until {gpu.frozen_until}, skipping")
                continue

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
            'grace_period_until': self.grace_period_until.isoformat() if self.grace_period_until else None,
            'shutdown_state': self.shutdown_state.value
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

        # Parse shutdown state
        shutdown_state = ShutdownState(data['shutdown_state']) if data.get('shutdown_state') else ShutdownState.NONE

        return cls(
            node_name=data['node_name'],
            address=data['address'],
            num_gpus=data['num_gpus'],
            gpus=gpus,
            status=status,
            last_heartbeat=last_heartbeat,
            registered_at=registered_at,
            grace_period_until=grace_period_until,
            shutdown_state=shutdown_state
        )

