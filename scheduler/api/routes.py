from typing import List, Optional
import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse

from scheduler.manager import JobManager, NodeManager
from scheduler.api.schemas import (
    JobSubmitRequest, JobResponse, JobListResponse,
    NodeRegisterRequest, NodeRegisterResponse, NodeHeartbeat, HeartbeatResponse, NodeResponse,
    GPUFreezeRequest
)
from scheduler.core import JobStatus, GPUStats, JobNotFoundException, NodeNotFoundException, constants, ShutdownState, RestartState
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
    async def heartbeat(node_name: str, request: NodeHeartbeat, timeout: Optional[int] = None):
        return await heartbeat_route(node_name, request, timeout)

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
    async def poll_job(node_name: str, timeout: int = 30):
        return await poll_job_route(node_name, timeout)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/complete")
    async def complete_job(job_id: str, exit_code: int, after_commit_ref: Optional[str] = None):
        return await complete_job_route(job_id, exit_code, after_commit_ref)

    @app.post(f"{constants.API_BASE_PATH}/workers/jobs/{{job_id}}/fail")
    async def fail_job(job_id: str, error_message: str, exit_code: Optional[int] = None, after_commit_ref: Optional[str] = None):
        return await fail_job_route(job_id, error_message, exit_code, after_commit_ref)

    # Cluster management routes
    @app.post(f"{constants.API_BASE_PATH}/shutdown/cluster")
    async def shutdown_cluster(background_tasks: BackgroundTasks):
        return await shutdown_cluster_route(background_tasks)

    @app.post(f"{constants.API_BASE_PATH}/restart/cluster")
    async def restart_cluster(timeout: Optional[int] = None):
        return await restart_cluster_route(timeout)

    # Log routes
    @app.get(f"{constants.API_BASE_PATH}/logs/head")
    async def get_head_logs(level: Optional[str] = None, limit: Optional[int] = None):
        return await get_head_logs_route(level, limit)

    # Git diff route
    @app.get(f"{constants.API_BASE_PATH}/jobs/{{job_id}}/diff")
    async def get_job_diff(job_id: str, compare_with: str = "end"):
        return await get_job_diff_route(job_id, compare_with)

    return app


# Route handlers

async def health_check_route() -> dict:
    """GET /api/v1/health - Health check"""
    return {"status": "healthy", "version": constants.API_VERSION}


async def submit_job_route(request: JobSubmitRequest) -> JobResponse:
    """POST /api/v1/jobs - Submit a job"""
    try:
        job = _job_manager.submit_job(
            command=request.command,
            requirements=request.requirements,
            name=request.name,
            working_dir=request.working_dir,
            env_vars=request.env_vars,
            dependencies=request.dependencies,
            priority=request.priority,
            job_id=request.job_id,
            snapshot_ref=request.snapshot_ref,
            snapshot_working_dir=request.snapshot_working_dir,
            conda_env=request.conda_env,
            restart=request.restart,
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
    
    try:
        return JobResponse.from_job(job)
    except Exception as e:
        # Handle corrupted job data gracefully
        logger.error(f"Failed to serialize job {job_id}: {e}. Job data may be corrupted.")
        logger.error(f"  Job details - exit_code: {job.exit_code} (type: {type(job.exit_code).__name__}), "
                    f"after_commit_ref: {job.after_commit_ref}, status: {job.status}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Job {job_id} has corrupted data and cannot be serialized. Please contact administrator."
        )


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
    
    # Convert jobs to responses with error handling for corrupted data
    job_responses = []
    for j in jobs:
        try:
            job_responses.append(JobResponse.from_job(j))
        except Exception as e:
            # Log the error but skip corrupted jobs instead of crashing
            logger.error(f"Failed to serialize job {j.job_id}: {e}. Job data may be corrupted.")
            logger.error(f"  Job details - exit_code: {j.exit_code} (type: {type(j.exit_code).__name__}), "
                        f"after_commit_ref: {j.after_commit_ref}, status: {j.status}")
            # Skip this job and continue with others
            continue
    
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
            num_gpus=request.num_gpus,
            restart_id=request.restart_id
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


async def heartbeat_route(
    node_name: str,
    request: NodeHeartbeat,
    timeout: Optional[int] = None
) -> HeartbeatResponse:
    """POST /api/v1/nodes/{node_name}/heartbeat - Send heartbeat and receive log requests"""
    try:
        # Convert dict stats to GPUStats objects
        gpu_stats = [GPUStats.from_dict(stat) for stat in request.gpu_stats]

        # Update heartbeat with shutdown_acknowledged flag
        _node_manager.update_heartbeat(
            node_name,
            gpu_stats,
            shutdown_acknowledged=request.shutdown_acknowledged,
            restart_acknowledged=request.restart_acknowledged
        )

        # Helper to get current job IDs (must be computed at response time, not request time,
        # to include jobs submitted during long-poll)
        def get_job_ids():
            return [job.job_id for job in _job_manager.jobs.values()]

        # Helper to get current rsync port
        def get_rsync_port():
            from scheduler.head import Orchestrator
            orchestrator = Orchestrator.get_instance()
            return orchestrator.rsync_port if orchestrator else None

        # Long-poll if timeout provided
        if timeout and timeout > 0:
            import time
            start = time.time()
            while time.time() - start < timeout:
                # Check if shutdown was requested
                node = _node_manager.get_node(node_name)
                if node and (node.shutdown_state != ShutdownState.NONE or node.restart_state == RestartState.REQUESTED):
                    recorded_job_ids = get_job_ids()
                    rsync_port = get_rsync_port()
                    return HeartbeatResponse(
                        status="ok",
                        shutdown_requested=node.shutdown_state != ShutdownState.NONE,
                        restart_requested=node.restart_state == RestartState.REQUESTED,
                        restart_id=node.restart_id if node.restart_state == RestartState.REQUESTED else None,
                        recorded_job_ids=recorded_job_ids,
                        running_job_ids=[],  # DEPRECATED: No longer used
                        rsync_port=rsync_port
                    )

                # Sleep briefly before checking again
                await asyncio.sleep(0.1)

        # Normal response (no shutdown, timeout reached or no timeout provided)
        recorded_job_ids = get_job_ids()
        rsync_port = get_rsync_port()
        node = _node_manager.get_node(node_name)
        return HeartbeatResponse(
            status="ok",
            shutdown_requested=False,
            restart_requested=bool(node and node.restart_state == RestartState.REQUESTED),
            restart_id=node.restart_id if node and node.restart_state == RestartState.REQUESTED else None,
            recorded_job_ids=recorded_job_ids,
            running_job_ids=[],  # DEPRECATED: No longer used
            rsync_port=rsync_port
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


async def poll_job_route(node_name: str, timeout: int = 30) -> List[JobResponse]:
    """
    GET /api/v1/workers/{node_name}/jobs/next - Long-poll for job assignment.

    Returns when:
    1. Event triggered (new job assigned) - returns all jobs immediately
    2. Timeout reached - returns all RUNNING jobs as recovery (or empty list if no jobs)

    The timeout recovery mechanism ensures jobs are delivered even if the event
    notification is missed due to race conditions or bugs.

    Args:
        node_name: Node name
        timeout: Timeout in seconds (default 30)

    Returns:
        List of jobs assigned to this node (empty list if no jobs)
    """
    # Check if node exists
    node = _node_manager.get_node(node_name)
    if not node:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node {node_name} not found")

    start_time = asyncio.get_event_loop().time()
    end_time = start_time + timeout

    # Check remaining time
    remaining_time = end_time - asyncio.get_event_loop().time()

    if remaining_time <= 0:
        # Timeout reached before even waiting
        logger.debug(f"Poll timeout for node {node_name}")
        return []

    # Return promptly when a restart is pending so workers can reach heartbeat/reexec quickly.
    node = _node_manager.get_node(node_name)
    if node and getattr(node, 'restart_state', RestartState.NONE) in (RestartState.REQUESTED, RestartState.ACKNOWLEDGED):
        logger.info(f"Returning empty poll response for node {node_name}; restart is pending")
        return []

    # Wait for job assignment event
    event = _job_manager.get_job_assignment_event(node_name)

    try:
        await asyncio.wait_for(event.wait(), timeout=remaining_time)
        # Event was set! Clear it and check for jobs
        event.clear()

        node = _node_manager.get_node(node_name)
        if node and getattr(node, 'restart_state', RestartState.NONE) in (RestartState.REQUESTED, RestartState.ACKNOWLEDGED):
            logger.info(f"Returning empty poll response for node {node_name}; restart is pending")
            return []

        # Find ALL RUNNING jobs assigned to this node
        running_jobs = _job_manager.get_running_jobs()
        node_jobs = [JobResponse.from_job(job)
                     for job in running_jobs
                     if job.assigned_node == node_name]

        if node_jobs:
            logger.info(f"Returning {len(node_jobs)} job(s) to node {node_name}: {[j.job_id for j in node_jobs]}")
        else:
            # Event was triggered but no job found (race condition: job completed quickly)
            logger.debug(f"Event triggered but no job found for node {node_name}")

        return node_jobs

    except asyncio.TimeoutError:
        node = _node_manager.get_node(node_name)
        if node and getattr(node, 'restart_state', RestartState.NONE) in (RestartState.REQUESTED, RestartState.ACKNOWLEDGED):
            logger.info(f"Returning empty poll response for node {node_name}; restart is pending")
            return []

        # Timeout reached - check for jobs as recovery mechanism
        # This handles cases where event notification was somehow missed
        running_jobs = _job_manager.get_running_jobs()
        node_jobs = [JobResponse.from_job(job)
                     for job in running_jobs
                     if job.assigned_node == node_name]

        if node_jobs:
            logger.info(f"Returning {len(node_jobs)} job(s) to node {node_name} (timeout recovery): {[j.job_id for j in node_jobs]}")
        else:
            # No jobs available
            logger.debug(f"Poll timeout for node {node_name}, no jobs available")

        return node_jobs


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


async def fail_job_route(job_id: str, error_message: str, exit_code: Optional[int] = None, after_commit_ref: Optional[str] = None):
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
        _job_manager.fail_job(job_id, error_message, exit_code, after_commit_ref)

        return {"status": "failed", "job_id": job_id}
    except JobNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error failing job: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


async def shutdown_cluster_route(background_tasks: BackgroundTasks) -> dict:
    """
    POST /api/v1/shutdown/cluster - Shutdown entire cluster

    Returns:
        Confirmation of shutdown status
    """
    try:
        logger.info("Cluster shutdown requested")

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

        # Do shutdown work directly (blocks until workers confirm)
        loop = asyncio.get_event_loop()
        all_confirmed = await loop.run_in_executor(
            None,
            orchestrator.shutdown_cluster_workers
        )

        # Schedule head shutdown AFTER response is sent
        background_tasks.add_task(orchestrator.stop)

        logger.info(f"Cluster shutdown completed: all_confirmed={all_confirmed}")
        return {
            "status": "shutdown_complete" if all_confirmed else "shutdown_timeout",
            "nodes_count": len(nodes),
            "all_confirmed": all_confirmed
        }

    except Exception as e:
        logger.error(f"Error during cluster shutdown: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to shutdown cluster: {e}"
        )


async def restart_cluster_route(timeout: Optional[int] = None) -> dict:
    """POST /api/v1/restart/cluster - Restart workers, then schedule head restart."""
    try:
        logger.info("Cluster restart requested")

        from scheduler.head import Orchestrator
        orchestrator = Orchestrator.get_instance()
        if not orchestrator:
            logger.error("Orchestrator instance not available")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Orchestrator not available"
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            orchestrator.restart_cluster,
            timeout
        )

        return result

    except Exception as e:
        logger.error(f"Error during cluster restart: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to restart cluster: {e}"
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


async def get_head_logs_route(level: Optional[str] = None, limit: Optional[int] = None) -> dict:
    """
    GET /api/v1/logs/head - Get head node logs (warnings and errors)

    Args:
        level: Filter by log level (WARNING or ERROR), None for all
        limit: Maximum number of entries to return, None for all

    Returns:
        Dictionary with log entries and statistics
    """
    from scheduler.core import parse_log_file, get_head_log_paths, load_config
    
    try:
        # Get head log paths
        config = load_config()
        head_log_paths = get_head_log_paths(config)
        
        all_logs = []
        stats = {"WARNING": 0, "ERROR": 0}

        # Process all available log files
        for log_path in head_log_paths:
            if os.path.exists(log_path):
                log_entries, log_stats = parse_log_file(log_path, limit=None)
                all_logs.extend(log_entries)
                
                # Update stats with log stats
                for level_key, count in log_stats.items():
                    if level_key in stats:
                        stats[level_key] += count

        # Sort all logs by timestamp (most recent first)
        all_logs = sorted(
            all_logs,
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        # Filter by level if specified
        if level:
            if level not in ["WARNING", "ERROR"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid level value: {level}. Valid values are: WARNING, ERROR"
                )
            filtered_logs = [log for log in all_logs if log.get('level') == level]
        else:
            filtered_logs = all_logs

        # Apply limit
        if limit:
            filtered_logs = filtered_logs[:limit]

        return {
            "logs": filtered_logs,
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting head logs: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def get_job_diff_route(job_id: str, compare_with: str = "end") -> dict:
    """GET /api/v1/jobs/{job_id}/diff - Get job git diff"""
    try:
        job = _job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found")

        if not job.snapshot_ref or not job.snapshot_working_dir:
             return {"diff": "No snapshot available for this job (not submitted from a git repo or snapshot failed)."}

        # Determine target ref
        target_ref = None
        if compare_with == "end":
            if not job.after_commit_ref:
                 return {"diff": "Job has not completed or no after-commit created (maybe no changes were made)."}
            target_ref = job.after_commit_ref
        elif compare_with == "current":
            target_ref = None # Compares snapshot_ref with current working directory
        else:
            return {"diff": f"Invalid compare_with mode: {compare_with}. Use 'end' or 'current'."}
        
        # Use GitSnapshotManager to get diff
        from scheduler.core import load_config
        from scheduler.worker import GitSnapshotManager
        
        config = load_config()
        git_manager = GitSnapshotManager(config)
        
        diff_output = git_manager.get_diff(job.snapshot_working_dir, job.snapshot_ref, target_ref)
        return {"diff": diff_output}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting diff for job {job_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
