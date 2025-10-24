from typing import List, Optional
import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.api.schemas import (
    JobSubmitRequest, JobResponse, JobListResponse,
    NodeRegisterRequest, NodeHeartbeat, NodeResponse
)
from scheduler.core import JobStatus, GPUStats, JobNotFoundException, NodeNotFoundException, constants

logger = logging.getLogger(__name__)

# Global references (will be set by create_app)
_job_manager: Optional[JobManager] = None
_node_manager: Optional[NodeManager] = None


def create_app(
    job_manager: JobManager,
    node_manager: NodeManager
) -> FastAPI:
    """
    Create FastAPI application with all routes.

    Args:
        job_manager: JobManager instance
        node_manager: NodeManager instance

    Returns:
        FastAPI application
    """
    global _job_manager, _node_manager
    _job_manager = job_manager
    _node_manager = node_manager

    app = FastAPI(
        title="GPU Scheduler API",
        version=constants.API_VERSION,
        docs_url=f"{constants.API_BASE_PATH}/docs"
    )

    # Health check
    @app.get(f"{constants.API_BASE_PATH}/health")
    async def health_check():
        return await health_check_route()

    # Job routes
    @app.post(f"{constants.API_BASE_PATH}/jobs", response_model=JobResponse)
    async def submit_job(request: JobSubmitRequest):
        return await submit_job_route(request)

    @app.get(f"{constants.API_BASE_PATH}/jobs/{{job_id}}", response_model=JobResponse)
    async def get_job(job_id: str):
        return await get_job_route(job_id)

    @app.get(f"{constants.API_BASE_PATH}/jobs", response_model=JobListResponse)
    async def list_jobs(status: Optional[str] = None, limit: Optional[int] = None):
        return await list_jobs_route(status, limit)

    @app.delete(f"{constants.API_BASE_PATH}/jobs/{{job_id}}")
    async def cancel_job(job_id: str):
        return await cancel_job_route(job_id)

    # Node routes
    @app.post(f"{constants.API_BASE_PATH}/nodes/register")
    async def register_node(request: NodeRegisterRequest):
        return await register_node_route(request)

    @app.post(f"{constants.API_BASE_PATH}/nodes/{{node_name}}/heartbeat")
    async def heartbeat(node_name: str, request: NodeHeartbeat):
        return await heartbeat_route(node_name, request)

    @app.get(f"{constants.API_BASE_PATH}/nodes", response_model=List[NodeResponse])
    async def list_nodes():
        return await list_nodes_route()

    @app.get(f"{constants.API_BASE_PATH}/nodes/{{node_name}}", response_model=NodeResponse)
    async def get_node(node_name: str):
        return await get_node_route(node_name)

    # Worker routes
    @app.get(f"{constants.API_BASE_PATH}/workers/{{node_name}}/jobs/next")
    async def poll_job(node_name: str):
        return await poll_job_route(node_name)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/complete")
    async def complete_job(job_id: str, exit_code: int):
        return await complete_job_route(job_id, exit_code)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/fail")
    async def fail_job(job_id: str, error_message: str):
        return await fail_job_route(job_id, error_message)

    return app


# Route handlers

async def health_check_route() -> dict:
    """GET /api/v1/health - Health check"""
    return {"status": "healthy", "version": constants.API_VERSION}


async def submit_job_route(request: JobSubmitRequest) -> JobResponse:
    """POST /api/v1/jobs - Submit a job"""
    try:
        job = _job_manager.submit_job(
            script=request.script,
            requirements=request.requirements,
            name=request.name,
            script_args=request.script_args,
            working_dir=request.working_dir,
            env_vars=request.env_vars,
            dependencies=request.dependencies,
            priority=request.priority,
            timeout=request.timeout
        )
        return JobResponse.from_job(job)
    except Exception as e:
        logger.error(f"Error submitting job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def get_job_route(job_id: str) -> JobResponse:
    """GET /api/v1/jobs/{job_id} - Get job details"""
    job = _job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")
    return JobResponse.from_job(job)


async def list_jobs_route(
    status: Optional[str] = None,
    limit: Optional[int] = None
) -> JobListResponse:
    """GET /api/v1/jobs - List jobs"""
    status_filter = None
    if status:
        try:
            status_filter = JobStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status value: {status}. Valid values are: {', '.join([s.value for s in JobStatus])}"
            )
    jobs = _job_manager.list_jobs(status_filter=status_filter, limit=limit)
    job_responses = [JobResponse.from_job(j) for j in jobs]
    return JobListResponse(jobs=job_responses, total=len(job_responses))


async def cancel_job_route(job_id: str):
    """DELETE /api/v1/jobs/{job_id} - Cancel a job"""
    try:
        _job_manager.cancel_job(job_id)
        return {"status": "cancelled", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


async def get_job_logs_route(
    job_id: str,
    lines: Optional[int] = None,
    stderr: bool = False
) -> str:
    """GET /api/v1/jobs/{job_id}/logs - Get job logs"""
    # This would read from log files - simplified for now
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Log retrieval not yet implemented")


async def stream_job_logs_route(job_id: str, stderr: bool = False):
    """GET /api/v1/jobs/{job_id}/logs/stream - Stream job logs (WebSocket)"""
    # This would use WebSocket - simplified for now
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Log streaming not yet implemented")


async def register_node_route(request: NodeRegisterRequest) -> dict:
    """POST /api/v1/nodes/register - Register a worker node"""
    try:
        node = _node_manager.register_node(
            node_name=request.node_name,
            address=request.address,
            num_gpus=request.num_gpus
        )
        return {"status": "registered", "node_name": node.node_name}
    except Exception as e:
        logger.error(f"Error registering node: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def heartbeat_route(node_name: str, request: NodeHeartbeat):
    """POST /api/v1/nodes/{node_name}/heartbeat - Send heartbeat"""
    try:
        # Convert dict stats to GPUStats objects
        gpu_stats = [GPUStats.from_dict(stat) for stat in request.gpu_stats]
        _node_manager.update_heartbeat(node_name, gpu_stats)
        return {"status": "ok"}
    except NodeNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error processing heartbeat: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def list_nodes_route() -> List[NodeResponse]:
    """GET /api/v1/nodes - List nodes"""
    nodes = _node_manager.list_nodes()
    return [NodeResponse.from_node(n) for n in nodes]


async def get_node_route(node_name: str) -> NodeResponse:
    """GET /api/v1/nodes/{node_name} - Get node details"""
    node = _node_manager.get_node(node_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_name} not found")
    return NodeResponse.from_node(node)


async def poll_job_route(node_name: str) -> Optional[JobResponse]:
    """GET /api/v1/workers/{node_name}/jobs/next - Poll for job (long-polling)"""
    # Check if node exists
    node = _node_manager.get_node(node_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_name} not found")

    # Find jobs assigned to this node that are running
    running_jobs = _job_manager.get_running_jobs()
    for job in running_jobs:
        if job.assigned_node == node_name:
            return JobResponse.from_job(job)

    # No job assigned
    return None


async def complete_job_route(job_id: str, exit_code: int):
    """POST /api/v1/workers/jobs/{job_id}/complete - Mark job complete"""
    try:
        job = _job_manager.get_job(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        # End grace period on the node (allow new jobs to be scheduled)
        # Note: We don't "release" GPUs - they become available naturally when
        # actual usage drops below threshold, as detected by pynvml monitoring
        if job.assigned_node:
            node = _node_manager.get_node(job.assigned_node)
            if node:
                node.grace_period_until = None

        # Mark job complete
        _job_manager.complete_job(job_id, exit_code)

        return {"status": "completed", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error completing job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def fail_job_route(job_id: str, error_message: str):
    """POST /api/v1/workers/jobs/{job_id}/fail - Mark job failed"""
    try:
        job = _job_manager.get_job(job_id)
        if not job:
            raise JobNotFoundException(f"Job {job_id} not found")

        # End grace period on the node (allow new jobs to be scheduled)
        # Note: We don't "release" GPUs - they become available naturally when
        # actual usage drops below threshold, as detected by pynvml monitoring
        if job.assigned_node:
            node = _node_manager.get_node(job.assigned_node)
            if node:
                node.grace_period_until = None

        # Mark job failed
        _job_manager.fail_job(job_id, error_message)

        return {"status": "failed", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error failing job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
