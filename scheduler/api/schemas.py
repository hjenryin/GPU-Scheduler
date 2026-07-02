from typing import Dict, List, Optional

from pydantic import BaseModel
from scheduler.core import Job, Node

class JobSubmitRequest(BaseModel):
    """Job submission request schema"""
    command: List[str]
    requirements: str
    name: Optional[str] = None
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    dependencies: Optional[List[str]] = None
    priority: int = 0
    job_id: Optional[str] = None
    snapshot_ref: Optional[str] = None
    snapshot_working_dir: Optional[str] = None
    conda_env: Optional[str] = None
    restart: Optional[str] = None


class JobResponse(BaseModel):
    """Job response schema"""
    job_id: str
    name: str
    command: List[str]
    requirements: str
    status: str
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_node: Optional[str] = None
    assigned_gpus: Optional[List[int]] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    dependencies: Optional[List[str]] = None
    priority: int = 0
    snapshot_ref: Optional[str] = None
    snapshot_working_dir: Optional[str] = None
    after_commit_ref: Optional[str] = None
    conda_env: Optional[str] = None
    eta: Optional[str] = None
    restarted: bool = False

    @classmethod
    def from_job(cls, job: Job) -> 'JobResponse':
        """Create response from Job model"""
        return cls(
            job_id=job.job_id,
            name=job.name,
            command=job.command,
            requirements=job.requirements.serialize(),  # Use serialize() for machine-readable format
            status=job.status.value,
            submitted_at=job.submitted_at.isoformat() if job.submitted_at else "",
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            assigned_node=job.assigned_node,
            assigned_gpus=job.assigned_gpus,
            exit_code=job.exit_code,
            error_message=job.error_message,
            working_dir=job.working_dir,
            env_vars=job.env_vars,
            dependencies=job.dependencies,
            priority=job.priority,
            snapshot_ref=job.snapshot_ref,
            snapshot_working_dir=job.snapshot_working_dir,
            after_commit_ref=job.after_commit_ref,
            conda_env=job.conda_env,
            eta=job.eta,
            restarted=job.restarted
        )


class JobListResponse(BaseModel):
    """Job list response schema"""
    jobs: List[JobResponse]
    total: int


class NodeRegisterRequest(BaseModel):
    """Node registration request schema"""
    node_name: str
    address: str
    num_gpus: int
    restart_id: Optional[str] = None


class NodeRegisterResponse(BaseModel):
    """Node registration response schema"""
    status: str
    node_name: str
    rsync_port: Optional[int] = None  # Port for log syncing, None if unavailable


class NodeHeartbeat(BaseModel):
    """Node heartbeat request schema"""
    gpu_stats: List[dict]  # List of GPUStats dicts
    shutdown_acknowledged: bool = False  # Worker confirms shutdown receipt
    restart_acknowledged: bool = False  # Worker confirms restart receipt


class HeartbeatResponse(BaseModel):
    """Head -> Worker: Heartbeat response"""
    status: str
    shutdown_requested: bool
    restart_requested: bool = False
    restart_id: Optional[str] = None
    recorded_job_ids: List[str] = []  # All job IDs for log file management (purge all others)
    running_job_ids: List[str] = []  # DEPRECATED: No longer used, kept for backward compatibility
    rsync_port: Optional[int] = None  # Current rsync port, workers should update if changed


class GPUFreezeRequest(BaseModel):
    """GPU freeze request schema"""
    duration_seconds: int  # Duration to freeze GPU in seconds


class GPUResponse(BaseModel):
    """GPU response schema"""
    gpu_id: int
    utilization: float
    memory_used: int
    memory_total: int
    temperature: int
    power_draw: int
    power_limit: Optional[int] = None
    running_job_id: Optional[str] = None
    frozen_until: Optional[str] = None
    assigned_job_id: Optional[str] = None
    user: Optional[str] = None
    stable_since: Optional[str] = None


class NodeResponse(BaseModel):
    """Node response schema"""
    node_name: str
    address: str
    num_gpus: int
    status: str
    gpus: List[GPUResponse]
    last_heartbeat: Optional[str] = None
    registered_at: str

    @classmethod
    def from_node(cls, node: Node) -> 'NodeResponse':
        """Create response from Node model"""
        gpus = [
            GPUResponse(
                gpu_id=gpu.gpu_id,
                utilization=gpu.stats.utilization,
                memory_used=gpu.stats.memory_used,
                memory_total=gpu.stats.memory_total,
                temperature=gpu.stats.temperature,
                power_draw=gpu.stats.power_draw,
                power_limit=gpu.stats.power_limit,
                running_job_id=gpu.stats.running_job_id,
                frozen_until=gpu.frozen_until.isoformat() if gpu.frozen_until else None,
                assigned_job_id=gpu.assigned_job_id,
                user=gpu.stats.user,
                stable_since=gpu.stable_since.isoformat() if gpu.stable_since else None
            )
            for gpu in node.gpus
        ]

        return cls(
            node_name=node.node_name,
            address=node.address,
            num_gpus=node.num_gpus,
            status=node.status.value,
            gpus=gpus,
            last_heartbeat=node.last_heartbeat.isoformat() if node.last_heartbeat else None,
            registered_at=node.registered_at.isoformat() if node.registered_at else ""
        )
