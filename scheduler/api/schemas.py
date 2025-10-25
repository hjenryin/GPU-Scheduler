from typing import Dict, List, Optional

from pydantic import BaseModel
from scheduler.core.models import Job, Node

class JobSubmitRequest(BaseModel):
    """Job submission request schema"""
    script: str
    requirements: str
    name: Optional[str] = None
    script_args: Optional[List[str]] = None
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    dependencies: Optional[List[str]] = None
    priority: int = 0


class JobResponse(BaseModel):
    """Job response schema"""
    job_id: str
    name: str
    script: str
    requirements: str
    status: str
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_node: Optional[str] = None
    assigned_gpus: Optional[List[int]] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    script_args: Optional[List[str]] = None
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    dependencies: Optional[List[str]] = None
    priority: int = 0

    @classmethod
    def from_job(cls, job: Job) -> 'JobResponse':
        """Create response from Job model"""
        return cls(
            job_id=job.job_id,
            name=job.name,
            script=job.script,
            requirements=job.requirements.serialize(),  # Use serialize() for machine-readable format
            status=job.status.value,
            submitted_at=job.submitted_at.isoformat() if job.submitted_at else "",
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            assigned_node=job.assigned_node,
            assigned_gpus=job.assigned_gpus,
            exit_code=job.exit_code,
            error_message=job.error_message,
            script_args=job.script_args,
            working_dir=job.working_dir,
            env_vars=job.env_vars,
            dependencies=job.dependencies,
            priority=job.priority
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


class NodeHeartbeat(BaseModel):
    """Node heartbeat request schema"""
    gpu_stats: List[dict]  # List of GPUStats dicts


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
