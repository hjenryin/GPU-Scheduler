from typing import List, Optional
from scheduler.head import JobManager, NodeManager
from scheduler.api import JobSubmitRequest, JobResponse, JobListResponse, NodeRegisterRequest, NodeHeartbeat, NodeResponse
from fastapi import FastAPI

def create_app(
    job_manager: JobManager,
    node_manager: NodeManager
) -> 'FastAPI':
    """
    Create FastAPI application with all routes.

    Args:
        job_manager: JobManager instance
        node_manager: NodeManager instance
        
    Returns:
        FastAPI application
    """
    pass

# Individual route handlers (used internally by create_app)


async def submit_job_route(request: 'JobSubmitRequest') -> 'JobResponse':
    """POST /api/v1/jobs - Submit a job"""
    pass


async def get_job_route(job_id: str) -> 'JobResponse':
    """GET /api/v1/jobs/{job_id} - Get job details"""
    pass


async def list_jobs_route(
    status: Optional[str] = None,
    limit: Optional[int] = None
) -> 'JobListResponse':
    """GET /api/v1/jobs - List jobs"""
    pass


async def cancel_job_route(job_id: str):
    """DELETE /api/v1/jobs/{job_id} - Cancel a job"""
    pass


async def get_job_logs_route(
    job_id: str,
    lines: Optional[int] = None,
    stderr: bool = False
) -> str:
    """GET /api/v1/jobs/{job_id}/logs - Get job logs"""
    pass


async def stream_job_logs_route(job_id: str, stderr: bool = False):
    """GET /api/v1/jobs/{job_id}/logs/stream - Stream job logs (WebSocket)"""
    pass


async def register_node_route(request: 'NodeRegisterRequest') -> dict:
    """POST /api/v1/nodes/register - Register a worker node"""
    pass


async def heartbeat_route(node_name: str, request: 'NodeHeartbeat'):
    """POST /api/v1/nodes/{node_name}/heartbeat - Send heartbeat"""
    pass


async def list_nodes_route() -> List['NodeResponse']:
    """GET /api/v1/nodes - List nodes"""
    pass


async def get_node_route(node_name: str) -> 'NodeResponse':
    """GET /api/v1/nodes/{node_name} - Get node details"""
    pass


async def poll_job_route(node_name: str) -> Optional['JobResponse']:
    """GET /api/v1/workers/{node_name}/jobs/next - Poll for job (long-polling)"""
    pass


async def complete_job_route(job_id: str, exit_code: int):
    """POST /api/v1/workers/jobs/{job_id}/complete - Mark job complete"""
    pass


async def fail_job_route(job_id: str, error_message: str):
    """POST /api/v1/workers/jobs/{job_id}/fail - Mark job failed"""
    pass


async def health_check_route() -> dict:
    """GET /api/v1/health - Health check"""
    pass
