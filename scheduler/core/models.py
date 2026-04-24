from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
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
    INTERRUPTED = "interrupted"
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
    user: Optional[str] = None

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        temperature: int,
        power_draw: int,
        power_limit: int,
        running_job_id: Optional[str] = None,
        user: Optional[str] = None
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
            running_job_id: ID of job using this GPU (if any)
            user: OS user of the process using this GPU (if any)
        """
        self.gpu_id = gpu_id
        self.utilization = utilization
        self.memory_used = memory_used
        self.memory_total = memory_total
        self.temperature = temperature
        self.power_draw = power_draw
        self.power_limit = power_limit
        self.running_job_id = running_job_id
        self.user = user

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
            'running_job_id': self.running_job_id,
            'user': self.user
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
            running_job_id=data.get('running_job_id'),
            user=data.get('user')
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
    frozen_until: Optional[datetime] = None
    assigned_job_id: Optional[str] = None

    def __init__(
        self,
        gpu_id: int,
        stats: GPUStats,
        frozen_until: Optional[datetime] = None,
        assigned_job_id: Optional[str] = None
    ):
        """
        Initialize GPU.

        Args:
            gpu_id: GPU index
            stats: Current GPU statistics
            frozen_until: Timestamp until which GPU is frozen (no jobs can run)
            assigned_job_id: ID of the job assigned to this GPU
        """
        self.gpu_id = gpu_id
        self.stats = stats
        self.frozen_until = frozen_until
        self.assigned_job_id = assigned_job_id

    def update_stats(self, stats: GPUStats):
        """Update GPU statistics.

        Args:
            stats: New GPU statistics
        """
        self.stats = stats

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

    def assign(self, job_id: str):
        """Assign GPU to a specific job."""
        self.assigned_job_id = job_id
        logger.info(f"GPU {self.gpu_id}: Assigned to job {self.assigned_job_id}")

    def unassign(self):
        """Unassign GPU."""
        logger.info(f"GPU {self.gpu_id}: Unassigned from job {self.assigned_job_id}")
        self.assigned_job_id = None

    def to_dict(self) -> dict:
        """Convert to dictionary representation.

        Returns:
            Dictionary containing GPU data
        """
        return {
            'gpu_id': self.gpu_id,
            'stats': self.stats.to_dict(),
            'frozen_until': self.frozen_until.isoformat() if self.frozen_until else None,
            'assigned_job_id': self.assigned_job_id
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'GPU':
        """Create GPU from dictionary.

        Args:
            data: Dictionary containing GPU data

        Returns:
            GPU instance
        """
        frozen_until = None
        if data.get('frozen_until'):
            frozen_until = datetime.fromisoformat(data['frozen_until'])

        assigned_job_id = data.get('assigned_job_id')

        return cls(
            gpu_id=data['gpu_id'],
            stats=GPUStats.from_dict(data['stats']),
            frozen_until=frozen_until,
            assigned_job_id=assigned_job_id
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
        """
        Parse requirement string into list of alternatives.

        num_gpus of -1 means flexible allocation (take all available GPUs on node).
        """
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
                # Try to parse as a number (any node with fixed count)
                try:
                    num_gpus = int(part)
                    if num_gpus <= 0:
                        raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
                    alternatives.append((None, num_gpus))
                except ValueError:
                    # Not a number, treat as hostname with flexible allocation
                    # e.g., "gpu1" means "take all available GPUs on gpu1"
                    node_name = part
                    if not node_name:
                        raise InvalidRequirementException(f"Invalid node name: {part}")
                    # Validate node name doesn't contain spaces (invalid format)
                    if ' ' in node_name:
                        raise InvalidRequirementException(f"Invalid requirement format: {part}. Use ':' to specify GPU count (e.g., 'gpu1:4')")
                    alternatives.append((node_name, -1))  # -1 = flexible allocation

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
            Machine-readable requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4", "gpu1")
        """
        parts = []
        for node_name, num_gpus in self._alternatives:
            if node_name is None:
                parts.append(str(num_gpus))
            elif num_gpus == -1:
                # Flexible allocation: just the node name
                parts.append(node_name)
            else:
                parts.append(f"{node_name}:{num_gpus}")
        return ",".join(parts)

    def __str__(self) -> str:
        """String representation of requirement for human display.

        Returns:
            Human-readable requirement string (e.g., "2 GPUs on any node", "all available GPUs on gpu1")
        """
        parts = []
        for node_name, num_gpus in self._alternatives:
            if node_name is None:
                parts.append(f"{num_gpus} GPUs on any node")
            elif num_gpus == -1:
                parts.append(f"all available GPUs on {node_name}")
            else:
                parts.append(f"{num_gpus} GPUs on {node_name}")
        return " OR ".join(parts)


class Job:
    """Job representation"""

    # Class attributes with defaults (enables create_autospec to work with spec_set)
    job_id: str = None
    name: str = None
    command: List[str] = None
    requirements: JobRequirement = None
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
    eta: Optional[str] = None
    restarted: bool = False

    def __init__(
        self,
        job_id: str,
        name: str,
        command: List[str],
        requirements: JobRequirement,
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
        conda_env: Optional[str] = None,
        eta: Optional[str] = None,
        restarted: bool = False
    ):
        """
        Initialize job.

        Args:
            job_id: Unique job identifier
            name: Human-readable job name
            command: Command to execute as a list (e.g., ["python", "train.py", "--epochs", "10"])
            requirements: JobRequirement instance
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
            eta: Estimated time to completion (parsed from tqdm output in stderr)
        """
        self.job_id = job_id
        self.name = name
        self.command = command if command else []
        self.requirements = requirements
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
        self.eta = eta
        self.restarted = restarted

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
            'command': self.command,
            'requirements': self.requirements.serialize(),
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
            'conda_env': self.conda_env,
            'eta': self.eta,
            'restarted': self.restarted
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

        # Handle migration from old format (script + script_args) to new format (command)
        # TEMPORARY MIGRATION CODE - Can be removed after all storage is migrated
        if 'command' in data:
            command = data['command']
        else:
            # Old format: convert script + script_args to command
            command = [data['script']]
            if data.get('script_args'):
                command.extend(data['script_args'])

        return cls(
            job_id=data['job_id'],
            name=data['name'],
            command=command,
            requirements=requirements,
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
            conda_env=data.get('conda_env'),
            eta=data.get('eta'),
            restarted=data.get('restarted', False)
        )


class JobSubmitRequest:
    """Schema for job submission requests.

    This provides a type-safe interface for building job submission payloads.
    Unlike the full Job class, this only contains fields needed for submission.
    """

    def __init__(
        self,
        job_id: str,
        command: List[str],
        requirements: str,
        working_dir: str,
        name: Optional[str] = None,
        env_vars: Optional[Dict[str, str]] = None,
        dependencies: Optional[List[str]] = None,
        priority: int = 0,
        snapshot_ref: Optional[str] = None,
        snapshot_working_dir: Optional[str] = None,
        conda_env: Optional[str] = None,
        restart: Optional[str] = None,
    ):
        """
        Initialize job submission request.

        Args:
            job_id: Unique job identifier
            command: Command to execute as a list (e.g., ["python", "train.py", "--epochs", "10"])
            requirements: Resource requirement string (e.g., "2", "gpu1:4")
            working_dir: Working directory for execution
            name: Human-readable job name
            env_vars: Environment variables
            dependencies: List of job IDs this job depends on
            priority: Job priority (higher = more important)
            snapshot_ref: Git snapshot reference
            snapshot_working_dir: Git snapshot working directory
            conda_env: Conda environment name
        """
        self.job_id = job_id
        self.command = command
        self.requirements = requirements
        self.working_dir = working_dir
        self.name = name
        self.env_vars = env_vars
        self.dependencies = dependencies
        self.priority = priority
        self.snapshot_ref = snapshot_ref
        self.snapshot_working_dir = snapshot_working_dir
        self.conda_env = conda_env
        self.restart = restart

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API payload."""
        return {
            "job_id": self.job_id,
            "command": self.command,
            "requirements": self.requirements,
            "working_dir": self.working_dir,
            "name": self.name,
            "env_vars": self.env_vars,
            "dependencies": self.dependencies,
            "priority": self.priority,
            "snapshot_ref": self.snapshot_ref,
            "snapshot_working_dir": self.snapshot_working_dir,
            "conda_env": self.conda_env,
            "restart": self.restart,
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

    def get_free_gpus(self, util_threshold: float, mem_threshold: float) -> List[int]:
        """Get list of free GPU IDs.

        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage

        Returns:
            List of GPU IDs that are free and not frozen (based on actual usage)
        """
        free_gpus = []
        for gpu in self.gpus:
            # Check if GPU is explicitly frozen or assigned
            is_frozen = gpu.is_frozen()
            if is_frozen:
                logger.debug(f"GPU {gpu.gpu_id}: frozen until {gpu.frozen_until}, skipping")
                continue
                
            if gpu.assigned_job_id is not None:
                logger.debug(f"GPU {gpu.gpu_id}: assigned to job {gpu.assigned_job_id}, skipping")
                continue

            # Check if GPU has low usage
            # We rely purely on actual GPU monitoring, not internal job tracking
            is_free = gpu.stats.is_free(util_threshold, mem_threshold)
            memory_percent = (gpu.stats.memory_used / gpu.stats.memory_total * 100) if gpu.stats.memory_total > 0 else 0
            logger.debug(f"GPU {gpu.gpu_id}: util={gpu.stats.utilization}%, mem={memory_percent:.1f}%, is_free={is_free}")
            if is_free:
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

