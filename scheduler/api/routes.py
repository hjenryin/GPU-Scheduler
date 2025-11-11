from typing import List, Optional
import logging
import os
import asyncio

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse

from scheduler.manager import JobManager, NodeManager
from scheduler.api.schemas import (
    JobSubmitRequest, JobResponse, JobListResponse,
    NodeRegisterRequest, NodeRegisterResponse, NodeHeartbeat, HeartbeatResponse, NodeResponse,
    GPUFreezeRequest
)
from scheduler.core import JobStatus, GPUStats, JobNotFoundException, NodeNotFoundException, constants
from scheduler.core import load_config

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

    @app.post(f"{constants.API_BASE_PATH}/jobs/{{job_id}}/retry-inplace")
    async def retry_job_inplace(job_id: str):
        return await retry_job_inplace_route(job_id)

    @app.get(f"{constants.API_BASE_PATH}/jobs/{{job_id}}/logs")
    async def get_job_logs(job_id: str, lines: Optional[int] = None, stderr: bool = False):
        return await get_job_logs_route(job_id, lines, stderr)

    @app.post(f"{constants.API_BASE_PATH}/jobs/{{job_id}}/purge")
    async def purge_job(job_id: str):
        return await purge_job_route(job_id)

    @app.post(f"{constants.API_BASE_PATH}/jobs/purge")
    async def purge_jobs(request: dict):
        return await purge_jobs_route(request)

    # Node routes
    @app.post(f"{constants.API_BASE_PATH}/nodes/register", response_model=NodeRegisterResponse)
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

    # GPU freeze/unfreeze routes
    @app.post(f"{constants.API_BASE_PATH}/nodes/{{node_name}}/gpus/{{gpu_id}}/freeze")
    async def freeze_gpu(node_name: str, gpu_id: int, request: GPUFreezeRequest):
        return await freeze_gpu_route(node_name, gpu_id, request)

    @app.post(f"{constants.API_BASE_PATH}/nodes/{{node_name}}/gpus/{{gpu_id}}/unfreeze")
    async def unfreeze_gpu(node_name: str, gpu_id: int):
        return await unfreeze_gpu_route(node_name, gpu_id)

    @app.post(f"{constants.API_BASE_PATH}/nodes/gpus/unfreeze")
    async def unfreeze_all_gpus():
        return await unfreeze_all_gpus_route()

    # Worker routes
    @app.get(f"{constants.API_BASE_PATH}/workers/{{node_name}}/jobs/next")
    async def poll_job(node_name: str):
        return await poll_job_route(node_name)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/complete")
    async def complete_job(job_id: str, exit_code: int, after_commit_ref: Optional[str] = None):
        return await complete_job_route(job_id, exit_code, after_commit_ref)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/fail")
    async def fail_job(job_id: str, error_message: str, after_commit_ref: Optional[str] = None):
        return await fail_job_route(job_id, error_message, after_commit_ref)

    # Cluster management routes
    @app.post(f"{constants.API_BASE_PATH}/shutdown/cluster")
    async def shutdown_cluster(graceful_timeout: int = 60, force: bool = False):
        return await shutdown_cluster_route(graceful_timeout, force)

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
            job_id=request.job_id,
            snapshot_ref=request.snapshot_ref,
            snapshot_working_dir=request.snapshot_working_dir,
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


async def retry_job_inplace_route(job_id: str):
    """POST /api/v1/jobs/{job_id}/retry-inplace - Retry a job in-place"""
    try:
        job = _job_manager.retry_job_inplace(job_id)
        return {"status": "retried", "job_id": job_id, "job": JobResponse.from_job(job).dict()}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def get_job_logs_route(
    job_id: str,
    lines: Optional[int] = None,
    stderr: bool = False
) -> str:
    """GET /api/v1/jobs/{job_id}/logs - Get job logs from head's storage"""
    try:
        # Verify job exists
        job = _job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

        # Read from head's log storage (logs are streamed from workers via heartbeat)
        import os
        from scheduler.core import load_config

        config = load_config()
        log_dir = os.path.expanduser(config.worker.log_dir)
        suffix = 'stderr' if stderr else 'stdout'
        log_filename = f"{job_id}.{suffix}.log"
        log_path = os.path.join(log_dir, log_filename)

        if not os.path.exists(log_path):
            # Log file doesn't exist yet
            if job.status.value == 'pending':
                return f"Logs not available for job {job_id}. Job is pending and has not started yet."
            else:
                return f"Logs not available for job {job_id}. Logs may still be transferring from worker."

        # Read logs from head's storage
        try:
            with open(log_path, 'r') as f:
                if lines is None:
                    content = f.read()
                else:
                    all_lines = f.readlines()
                    content = ''.join(all_lines[-lines:])
            return content
        except Exception as e:
            logger.error(f"Failed to read log file {log_path}: {e}")
            return f"Error reading log file: {e}"

    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving logs for job {job_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def register_node_route(request: NodeRegisterRequest) -> NodeRegisterResponse:
    """POST /api/v1/nodes/register - Register a worker node"""
    try:
        node = _node_manager.register_node(
            node_name=request.node_name,
            address=request.address,
            num_gpus=request.num_gpus
        )

        # Get rsync port from orchestrator
        from scheduler.head import Orchestrator
        orchestrator = Orchestrator.get_instance()
        rsync_port = orchestrator.rsync_port if orchestrator else None

        return NodeRegisterResponse(
            status="registered",
            node_name=node.node_name,
            rsync_port=rsync_port
        )
    except Exception as e:
        logger.error(f"Error registering node: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def heartbeat_route(node_name: str, request: NodeHeartbeat) -> HeartbeatResponse:
    """POST /api/v1/nodes/{node_name}/heartbeat - Send heartbeat and receive log requests"""
    try:
        # Convert dict stats to GPUStats objects
        gpu_stats = [GPUStats.from_dict(stat) for stat in request.gpu_stats]
        _node_manager.update_heartbeat(node_name, gpu_stats)

        # Get ALL job IDs across all workers (not just this node)
        # This prevents workers from purging logs of jobs running on other nodes
        # when the head and worker share the same log directory
        recorded_job_ids = [job.job_id for job in _job_manager.jobs.values()]

        # Get RUNNING job IDs assigned to THIS worker only
        # Worker should terminate processes not in this list (after grace period)
        running_job_ids = [
            job.job_id
            for job in _job_manager.jobs.values()
            if job.status == JobStatus.RUNNING and job.assigned_node == node_name
        ]

        # Check if shutdown has been requested for this node
        node = _node_manager.get_node(node_name)
        shutdown_requested = node.shutdown_requested if node else False

        return HeartbeatResponse(
            status="ok",
            shutdown_requested=shutdown_requested,
            recorded_job_ids=recorded_job_ids,
            running_job_ids=running_job_ids
        )
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


async def complete_job_route(job_id: str, exit_code: int, after_commit_ref: Optional[str] = None):
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
        _job_manager.complete_job(job_id, exit_code, after_commit_ref)

        return {"status": "completed", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error completing job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def fail_job_route(job_id: str, error_message: str, after_commit_ref: Optional[str] = None):
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
        _job_manager.fail_job(job_id, error_message, after_commit_ref)

        return {"status": "failed", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error failing job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def shutdown_cluster_route(graceful_timeout: int = 60, force: bool = False) -> dict:
    """
    POST /api/v1/shutdown/cluster - Shutdown entire cluster

    This endpoint implements long polling: it won't return until all workers
    have acknowledged the shutdown signal and the head is ready to shut down.
    The response is sent right before the head node shuts down.

    Args:
        graceful_timeout: Seconds to wait for graceful shutdown
        force: Whether to force kill if graceful shutdown fails

    Returns:
        Confirmation of shutdown completion (sent right before head shuts down)
    """
    try:
        logger.info(f"Cluster shutdown requested: graceful_timeout={graceful_timeout}, force={force}")

        # Get all connected nodes
        nodes = _node_manager.get_connected_nodes()
        logger.info(f"Found {len(nodes)} connected nodes to shutdown")

        # Signal orchestrator to shutdown cluster
        from scheduler.head import Orchestrator
        orchestrator = Orchestrator.get_instance()
        if not orchestrator:
            logger.error("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Orchestrator not available"
            )

        # Initiate shutdown in background thread
        orchestrator.request_cluster_shutdown(graceful_timeout, force)
        logger.info("Cluster shutdown initiated, waiting for workers to acknowledge...")

        # Wait for shutdown to be ready (workers acknowledged)
        # Use a generous timeout: graceful_timeout + 30 seconds for worker acknowledgment
        wait_timeout = graceful_timeout + 30
        loop = asyncio.get_event_loop()

        # Run the blocking wait in a thread pool to avoid blocking the event loop
        shutdown_ready = await loop.run_in_executor(
            None,
            orchestrator.wait_for_shutdown_ready,
            wait_timeout
        )

        if shutdown_ready:
            logger.info("All workers acknowledged shutdown, head will shut down now")
            return {
                "status": "shutdown_complete",
                "nodes_count": len(nodes),
                "graceful_timeout": graceful_timeout,
                "force": force,
                "message": "All workers acknowledged shutdown, head shutting down"
            }
        else:
            logger.warning(f"Shutdown ready timeout after {wait_timeout}s, forcing shutdown")
            return {
                "status": "shutdown_timeout",
                "nodes_count": len(nodes),
                "graceful_timeout": graceful_timeout,
                "force": force,
                "message": f"Timeout waiting for workers, head shutting down anyway"
            }

    except Exception as e:
        logger.error(f"Error during cluster shutdown: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete cluster shutdown: {e}"
        )


async def purge_job_route(job_id: str) -> dict:
    """
    POST /api/v1/jobs/{job_id}/purge - Purge a specific job
    
    Args:
        job_id: Job ID to purge
    
    Returns:
        Confirmation of purge initiation
    """
    try:
        _job_manager.purge_job(job_id)
        logger.info(f"Job {job_id} marked for purging")
        return {
            "status": "purge_initiated",
            "job_id": job_id
        }
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error purging job {job_id}: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def purge_jobs_route(request: dict) -> dict:
    """
    POST /api/v1/jobs/purge - Purge jobs based on criteria

    Args:
        request: Dict with 'before_time' (ISO format) and 'status_filter' (list)

    Returns:
        Response with purged_count
    """
    try:
        from datetime import datetime

        before_time = None
        if 'before_time' in request:
            before_time = datetime.fromisoformat(request['before_time'])

        status_filter = request.get('status_filter', None)

        purged_count = _job_manager.purge_jobs_by_criteria(
            before_time=before_time,
            status_filter=status_filter
        )

        logger.info(f"Marked {purged_count} jobs for purging")
        return {
            "status": "purge_initiated",
            "purged_count": purged_count
        }
    except Exception as e:
        logger.error(f"Error purging jobs: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def freeze_gpu_route(node_name: str, gpu_id: int, request: GPUFreezeRequest) -> dict:
    """
    POST /api/v1/nodes/{node_name}/gpus/{gpu_id}/freeze - Freeze a GPU

    Args:
        node_name: Name of the node
        gpu_id: GPU ID to freeze
        request: Freeze request containing duration

    Returns:
        Confirmation of freeze operation
    """
    try:
        node = _node_manager.get_node(node_name)
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_name} not found")

        if gpu_id < 0 or gpu_id >= len(node.gpus):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GPU ID {gpu_id}. Node {node_name} has {len(node.gpus)} GPUs (0-{len(node.gpus)-1})"
            )

        gpu = node.gpus[gpu_id]
        gpu.freeze(request.duration_seconds)

        # Save node state to persist freeze
        _node_manager.save_node(node)

        logger.info(f"GPU {gpu_id} on node {node_name} frozen for {request.duration_seconds} seconds")
        return {
            "status": "frozen",
            "node_name": node_name,
            "gpu_id": gpu_id,
            "frozen_until": gpu.frozen_until.isoformat() if gpu.frozen_until else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error freezing GPU {gpu_id} on node {node_name}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def unfreeze_gpu_route(node_name: str, gpu_id: int) -> dict:
    """
    POST /api/v1/nodes/{node_name}/gpus/{gpu_id}/unfreeze - Unfreeze a GPU

    Args:
        node_name: Name of the node
        gpu_id: GPU ID to unfreeze

    Returns:
        Confirmation of unfreeze operation
    """
    try:
        node = _node_manager.get_node(node_name)
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_name} not found")

        if gpu_id < 0 or gpu_id >= len(node.gpus):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid GPU ID {gpu_id}. Node {node_name} has {len(node.gpus)} GPUs (0-{len(node.gpus)-1})"
            )

        gpu = node.gpus[gpu_id]
        gpu.unfreeze()

        # Save node state to persist unfreeze
        _node_manager.save_node(node)

        logger.info(f"GPU {gpu_id} on node {node_name} unfrozen")
        return {
            "status": "unfrozen",
            "node_name": node_name,
            "gpu_id": gpu_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error unfreezing GPU {gpu_id} on node {node_name}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def unfreeze_all_gpus_route() -> dict:
    """
    POST /api/v1/nodes/gpus/unfreeze - Unfreeze all GPUs across all nodes

    Returns:
        Confirmation with count of unfrozen GPUs
    """
    try:
        nodes = _node_manager.list_nodes()
        unfrozen_count = 0

        for node in nodes:
            for gpu in node.gpus:
                if gpu.is_frozen():
                    gpu.unfreeze()
                    unfrozen_count += 1

            # Save node state to persist unfreeze
            _node_manager.save_node(node)

        logger.info(f"Unfrozen {unfrozen_count} GPUs across all nodes")
        return {
            "status": "unfrozen",
            "unfrozen_count": unfrozen_count
        }
    except Exception as e:
        logger.error(f"Error unfreezing all GPUs: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
