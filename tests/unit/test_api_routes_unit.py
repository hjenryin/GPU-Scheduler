"""Unit tests for API route functions with proper mocking"""
import pytest
from unittest.mock import Mock, patch, MagicMock, create_autospec
from fastapi import HTTPException

from scheduler.api.routes import (
    health_check_route,
    submit_job_route,
    get_job_route,
    list_jobs_route,
    cancel_job_route,
    get_job_logs_route,
    register_node_route,
    heartbeat_route,
    list_nodes_route,
    get_node_route,
    poll_job_route,
    complete_job_route,
    fail_job_route,
    shutdown_cluster_route,
    purge_job_route,
    purge_jobs_route,
    freeze_gpu_route,
    unfreeze_gpu_route,
    unfreeze_all_gpus_route
)
from scheduler.api.schemas import (
    JobSubmitRequest, NodeRegisterRequest, NodeHeartbeat,
    NodeRegisterResponse, GPUFreezeRequest
)
from scheduler.core.models import Job, JobStatus, JobRequirement, Node, NodeStatus, GPUStats, GPU
from scheduler.core.exceptions import JobNotFoundException, NodeNotFoundException
from scheduler.head.orchestrator import Orchestrator


class TestNodeRegisterResponseSchema:
    """Tests for NodeRegisterResponse schema"""

    def test_node_register_response_with_rsync_port(self):
        """Test NodeRegisterResponse schema with rsync_port"""
        response = NodeRegisterResponse(
            status="registered",
            node_name="node1",
            rsync_port=8873
        )

        assert response.status == "registered"
        assert response.node_name == "node1"
        assert response.rsync_port == 8873

    def test_node_register_response_without_rsync_port(self):
        """Test NodeRegisterResponse schema without rsync_port"""
        response = NodeRegisterResponse(
            status="registered",
            node_name="node1"
        )

        assert response.status == "registered"
        assert response.node_name == "node1"
        assert response.rsync_port is None

    def test_node_register_response_with_none_rsync_port(self):
        """Test NodeRegisterResponse schema with explicitly None rsync_port"""
        response = NodeRegisterResponse(
            status="registered",
            node_name="node1",
            rsync_port=None
        )

        assert response.status == "registered"
        assert response.node_name == "node1"
        assert response.rsync_port is None

    def test_node_register_response_serialization(self):
        """Test NodeRegisterResponse serialization"""
        response = NodeRegisterResponse(
            status="registered",
            node_name="node1",
            rsync_port=8873
        )

        # Test model_dump (Pydantic v2)
        data = response.model_dump()
        assert data['status'] == "registered"
        assert data['node_name'] == "node1"
        assert data['rsync_port'] == 8873


# Fixture-based mocking with autospec
@pytest.fixture
def mock_job_manager():
    """Mocks the _job_manager in the routes file with autospec."""
    from scheduler.manager import JobManager
    from unittest.mock import create_autospec
    
    # Use create_autospec with spec_set for internal classes
    mock_jm = create_autospec(JobManager, instance=True, spec_set=True)
    mock_jm.jobs = {}  # Add jobs attribute as empty dict
    
    with patch('scheduler.api.routes._job_manager', mock_jm):
        yield mock_jm


@pytest.fixture
def mock_node_manager():
    """Mocks the _node_manager in the routes file with autospec."""
    # Use Mock with spec instead of autospec on already-mocked attributes
    from scheduler.manager import NodeManager
    mock_nm = MagicMock(spec=NodeManager)
    
    with patch('scheduler.api.routes._node_manager', mock_nm):
        yield mock_nm


@pytest.fixture
def mock_logger():
    """Mocks the logger in the routes file."""
    with patch('scheduler.api.routes.logger') as mock_log:
        yield mock_log


class TestHealthCheckRoute:
    """Tests for health_check_route"""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check returns healthy status"""
        result = await health_check_route()
        
        assert result['status'] == 'healthy'
        assert 'version' in result


class TestSubmitJobRoute:
    """Tests for submit_job_route"""

    @pytest.mark.asyncio
    async def test_submit_job_success(self, mock_job_manager):
        """Test successful job submission"""
        request = JobSubmitRequest(
            script="/path/script.py",
            requirements="2",
            name="test_job"
        )
        
        mock_job = Job(
            job_id="job_123",
            name="test_job",
            script="/path/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.PENDING
        )
        mock_job_manager.submit_job.return_value = mock_job
        
        result = await submit_job_route(request)
        
        assert result.job_id == "job_123"
        assert result.status == JobStatus.PENDING.value
        mock_job_manager.submit_job.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_job_with_all_parameters(self, mock_job_manager):
        """Test submit with all optional parameters"""
        request = JobSubmitRequest(
            script="/path/script.py",
            requirements="4",
            name="my-job",
            script_args=['arg1', 'arg2'],
            working_dir="/tmp",
            env_vars={'KEY': 'value'},
            dependencies=['job-1', 'job-2'],
            priority=5
        )
        
        mock_job = Job(
            job_id="job_123",
            name="my-job",
            script="/path/script.py",
            requirements=JobRequirement("4"),
            status=JobStatus.PENDING
        )
        mock_job_manager.submit_job.return_value = mock_job
        
        result = await submit_job_route(request)
        
        assert result.job_id == "job_123"
        # Verify all parameters passed through
        call_kwargs = mock_job_manager.submit_job.call_args[1]
        assert call_kwargs['script'] == "/path/script.py"
        assert call_kwargs['requirements'] == "4"
        assert call_kwargs['name'] == "my-job"

    @pytest.mark.asyncio
    async def test_submit_job_exception(self, mock_logger, mock_job_manager):
        """Test submit job with exception"""
        request = JobSubmitRequest(
            script="/path/script.py",
            requirements="2",
            name="test_job"
        )
        
        mock_job_manager.submit_job.side_effect = Exception("Submission error")
        
        with pytest.raises(HTTPException) as exc_info:
            await submit_job_route(request)
        
        assert exc_info.value.status_code == 400
        mock_logger.error.assert_called_once()


class TestGetJobRoute:
    """Tests for get_job_route"""

    @pytest.mark.asyncio
    async def test_get_job_success(self, mock_job_manager):
        """Test getting a job successfully"""
        mock_job = Job(
            job_id="job_123",
            name="test_job",
            script="/path/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.RUNNING
        )
        mock_job_manager.get_job.return_value = mock_job
        
        result = await get_job_route("job_123")
        
        assert result.job_id == "job_123"
        assert result.status == JobStatus.RUNNING.value
        mock_job_manager.get_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_get_job_not_found(self, mock_job_manager):
        """Test getting a non-existent job returns 404"""
        # Route checks if job is None, not exception
        mock_job_manager.get_job.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_job_route("nonexistent")
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_get_job_with_exit_code(self, mock_job_manager):
        """Test getting a completed job with exit code"""
        from datetime import datetime
        
        mock_job = Job(
            job_id="job_123",
            name="test_job",
            script="/path/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.COMPLETED,
            exit_code=0,
            completed_at=datetime.now()
        )
        mock_job_manager.get_job.return_value = mock_job
        
        result = await get_job_route("job_123")
        
        assert result.status == JobStatus.COMPLETED.value
        assert result.exit_code == 0


class TestListJobsRoute:
    """Tests for list_jobs_route"""

    @pytest.mark.asyncio
    async def test_list_jobs_empty(self, mock_job_manager):
        """Test listing jobs when empty"""
        mock_job_manager.list_jobs.return_value = []
        
        result = await list_jobs_route()
        
        assert result.jobs == []
        assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_jobs_with_one_job(self, mock_job_manager):
        """Test listing jobs with one job"""
        mock_job = Job(
            job_id="job_123",
            name="test",
            script="/path/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        mock_job_manager.list_jobs.return_value = [mock_job]
        
        result = await list_jobs_route()
        
        assert result.total == 1
        assert len(result.jobs) == 1
        assert result.jobs[0].job_id == "job_123"

    @pytest.mark.asyncio
    async def test_list_jobs_with_status_filter(self, mock_job_manager):
        """Test listing jobs with status filter"""
        mock_job = Job(
            job_id="job_123",
            name="test",
            script="/path/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.RUNNING
        )
        mock_job_manager.list_jobs.return_value = [mock_job]
        
        result = await list_jobs_route(status='running', limit=10)
        
        assert result.total == 1
        mock_job_manager.list_jobs.assert_called_once_with(status_filter=JobStatus.RUNNING, limit=10)

    @pytest.mark.asyncio
    async def test_list_jobs_with_limit(self, mock_job_manager):
        """Test listing jobs with limit parameter"""
        mock_job_manager.list_jobs.return_value = []
        
        await list_jobs_route(status=None, limit=5)
        
        mock_job_manager.list_jobs.assert_called_once_with(status_filter=None, limit=5)


class TestCancelJobRoute:
    """Tests for cancel_job_route"""

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, mock_job_manager):
        """Test successful job cancellation"""
        mock_job_manager.cancel_job.return_value = True
        
        result = await cancel_job_route("job_123")
        
        assert result['status'] == "cancelled"
        assert result['job_id'] == "job_123"
        mock_job_manager.cancel_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, mock_job_manager):
        """Test canceling a non-existent job returns 404"""
        mock_job_manager.cancel_job.side_effect = JobNotFoundException("Job not found")
        
        with pytest.raises(HTTPException) as exc_info:
            await cancel_job_route("nonexistent")
        
        assert exc_info.value.status_code == 404


class TestListJobsRouteValidation:
    """Tests for list_jobs_route validation"""

    @pytest.mark.asyncio
    async def test_list_jobs_invalid_status(self, mock_job_manager):
        """Test that invalid status filter returns 400"""
        with pytest.raises(HTTPException) as exc_info:
            await list_jobs_route(status='invalid_status')
        
        assert exc_info.value.status_code == 400
        assert "Invalid status value" in str(exc_info.value.detail)


class TestGetJobLogsRoute:
    """Tests for get_job_logs_route"""

    @pytest.mark.asyncio
    async def test_get_job_logs_job_not_found(self, mock_job_manager):
        """Test retrieving logs for non-existent job"""
        mock_job_manager.get_job.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_job_logs_route("nonexistent")
        
        assert exc_info.value.status_code == 500  # Route catches and returns 500


class TestRegisterNodeRoute:
    """Tests for register_node_route"""

    @pytest.mark.asyncio
    async def test_register_node_success(self, mock_node_manager):
        """Test successful node registration"""
        # Create a proper mock that respects Node's interface
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.node_name = "node1"
        mock_node_manager.register_node.return_value = mock_node

        request = NodeRegisterRequest(
            node_name="node1",
            address="localhost:9000",
            num_gpus=4
        )

        result = await register_node_route(request)

        assert result.status == "registered"
        assert result.node_name == "node1"
        mock_node_manager.register_node.assert_called_once()

    @pytest.mark.asyncio
    async def test_register_node_error(self, mock_node_manager):
        """Test node registration with error"""
        mock_node_manager.register_node.side_effect = Exception("Registration failed")

        request = NodeRegisterRequest(
            node_name="node1",
            address="localhost:9000",
            num_gpus=4
        )

        with pytest.raises(HTTPException) as exc_info:
            await register_node_route(request)

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_register_node_returns_rsync_port(self, mock_node_manager):
        """Test node registration returns rsync_port from orchestrator"""
        from scheduler.head import Orchestrator

        # Create a proper mock that respects Node's interface
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.node_name = "node1"
        mock_node_manager.register_node.return_value = mock_node

        # Mock orchestrator with rsync_port
        mock_orchestrator = create_autospec(Orchestrator, instance=True, spec_set=True)
        mock_orchestrator.rsync_port = 8873

        with patch.object(Orchestrator, 'get_instance', return_value=mock_orchestrator):
            request = NodeRegisterRequest(
                node_name="node1",
                address="localhost:9000",
                num_gpus=4
            )

            result = await register_node_route(request)

            assert result.status == "registered"
            assert result.node_name == "node1"
            assert result.rsync_port == 8873

    @pytest.mark.asyncio
    async def test_register_node_returns_none_when_rsync_unavailable(self, mock_node_manager):
        """Test node registration returns None rsync_port when unavailable"""
        from scheduler.head import Orchestrator

        # Create a proper mock that respects Node's interface
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.node_name = "node1"
        mock_node_manager.register_node.return_value = mock_node

        # Mock orchestrator with no rsync_port
        mock_orchestrator = create_autospec(Orchestrator, instance=True, spec_set=True)
        mock_orchestrator.rsync_port = None

        with patch.object(Orchestrator, 'get_instance', return_value=mock_orchestrator):
            request = NodeRegisterRequest(
                node_name="node1",
                address="localhost:9000",
                num_gpus=4
            )

            result = await register_node_route(request)

            assert result.status == "registered"
            assert result.node_name == "node1"
            assert result.rsync_port is None


class TestHeartbeatRoute:
    """Tests for heartbeat_route"""

    @pytest.mark.asyncio
    async def test_heartbeat_success(self, mock_job_manager, mock_node_manager):
        """Test successful heartbeat"""
        request = NodeHeartbeat(gpu_stats=[])
        
        result = await heartbeat_route("node1", request)
        
        assert result.status == "ok"
        mock_node_manager.update_heartbeat.assert_called_once()

    @pytest.mark.asyncio
    async def test_heartbeat_node_not_found(self, mock_node_manager):
        """Test heartbeat for non-existent node"""
        from scheduler.core.exceptions import NodeNotFoundException
        request = NodeHeartbeat(gpu_stats=[])
        mock_node_manager.update_heartbeat.side_effect = NodeNotFoundException("Node not found")
        
        with pytest.raises(HTTPException) as exc_info:
            await heartbeat_route("nonexistent", request)
        
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_heartbeat_error(self, mock_node_manager):
        """Test heartbeat with error"""
        request = NodeHeartbeat(gpu_stats=[])
        mock_node_manager.update_heartbeat.side_effect = Exception("Error")
        
        with pytest.raises(HTTPException) as exc_info:
            await heartbeat_route("node1", request)
        
        assert exc_info.value.status_code == 400  # Route returns 400 for generic errors

    @pytest.mark.asyncio
    async def test_heartbeat_returns_shutdown_flag(self, mock_job_manager, mock_node_manager):
        """Test heartbeat returns shutdown_requested flag"""
        from unittest.mock import Mock
        from scheduler.core import ShutdownState
        request = NodeHeartbeat(gpu_stats=[], timeout=1)  # With timeout to trigger long-poll
        
        # Mock node with shutdown requested
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.shutdown_state = ShutdownState.SENT
        mock_node_manager.get_node.return_value = mock_node
        
        result = await heartbeat_route("node1", request, timeout=1)
        
        assert result.status == "ok"
        assert result.shutdown_requested == True
        mock_node_manager.update_heartbeat.assert_called_once()
        mock_node_manager.get_node.assert_called()

    @pytest.mark.asyncio
    async def test_heartbeat_no_shutdown_requested(self, mock_job_manager, mock_node_manager):
        """Test heartbeat when shutdown not requested"""
        from unittest.mock import Mock
        request = NodeHeartbeat(gpu_stats=[])
        
        # Mock node without shutdown requested
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.shutdown_requested = False
        mock_node_manager.get_node.return_value = mock_node
        
        result = await heartbeat_route("node1", request)
        
        assert result.status == "ok"
        assert result.shutdown_requested == False


class TestListNodesRoute:
    """Tests for list_nodes_route"""

    @pytest.mark.asyncio
    async def test_list_nodes_empty(self, mock_node_manager):
        """Test listing nodes when empty"""
        from scheduler.api.routes import list_nodes_route
        
        mock_node_manager.list_nodes.return_value = []
        
        result = await list_nodes_route()
        
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_list_nodes_with_nodes(self, mock_node_manager):
        """Test listing nodes with data"""
        from scheduler.api.routes import list_nodes_route
        
        mock_node = Node(
            node_name="node1",
            address="localhost:9000",
            num_gpus=4
        )
        mock_node_manager.list_nodes.return_value = [mock_node]
        
        result = await list_nodes_route()
        
        assert len(result) == 1
        assert result[0].node_name == "node1"


class TestGetNodeRoute:
    """Tests for get_node_route"""

    @pytest.mark.asyncio
    async def test_get_node_success(self, mock_node_manager):
        """Test getting a node successfully"""
        from scheduler.api.routes import get_node_route
        
        mock_node = Node(
            node_name="node1",
            address="localhost:9000",
            num_gpus=4
        )
        mock_node_manager.get_node.return_value = mock_node
        
        result = await get_node_route("node1")
        
        assert result.node_name == "node1"
        mock_node_manager.get_node.assert_called_once_with("node1")

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, mock_node_manager):
        """Test getting a non-existent node"""
        from scheduler.api.routes import get_node_route
        
        mock_node_manager.get_node.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_node_route("nonexistent")
        
        assert exc_info.value.status_code == 404


class TestPollJobRoute:
    """Tests for poll_job_route"""

    @pytest.mark.asyncio
    async def test_poll_job_with_job(self, mock_node_manager, mock_job_manager):
        """Test polling for job when available"""
        from scheduler.api.routes import poll_job_route
        
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.node_name = "node1"
        mock_node_manager.get_node.return_value = mock_node
        
        mock_job = Job(
            job_id="job_123",
            name="test",
            script="/path/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.RUNNING,
            assigned_node="node1"
        )
        mock_job_manager.get_running_jobs.return_value = [mock_job]
        
        result = await poll_job_route("node1")
        
        assert result.job_id == "job_123"

    @pytest.mark.asyncio
    async def test_poll_job_no_job(self, mock_job_manager, mock_node_manager):
        """Test polling for job when no job available"""
        from scheduler.api.routes import poll_job_route
        
        mock_job_manager.get_running_jobs.return_value = []  # No running jobs
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)  # Need a valid node
        
        result = await poll_job_route("node1")
        
        assert result is None


class TestCompleteJobRoute:
    """Tests for complete_job_route"""

    @pytest.mark.asyncio
    async def test_complete_job_success(self, mock_job_manager, mock_node_manager):
        """Test successful job completion"""
        from scheduler.api.routes import complete_job_route

        # Mock both managers
        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        result = await complete_job_route("job_123", exit_code=0)
        
        assert result['status'] == "completed"
        mock_job_manager.complete_job.assert_called_once_with("job_123", 0, None)

    @pytest.mark.asyncio
    async def test_complete_job_not_found(self, mock_job_manager, mock_node_manager):
        """Test completing a non-existent job"""
        from scheduler.api.routes import complete_job_route
        
        mock_job_manager.get_job.return_value = None
        mock_job_manager.complete_job.side_effect = JobNotFoundException("Job not found")
        
        with pytest.raises(HTTPException) as exc_info:
            await complete_job_route("nonexistent", 0)
        
        assert exc_info.value.status_code == 404


class TestFailJobRoute:
    """Tests for fail_job_route"""

    @pytest.mark.asyncio
    async def test_fail_job_success(self, mock_job_manager, mock_node_manager):
        """Test successful job failure"""
        from scheduler.api.routes import fail_job_route

        # Mock both managers
        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        result = await fail_job_route("job_123", "Error occurred")
        
        assert result['status'] == "failed"
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred", None)

    @pytest.mark.asyncio
    async def test_fail_job_not_found(self, mock_job_manager, mock_node_manager):
        """Test failing a non-existent job"""
        from scheduler.api.routes import fail_job_route
        
        mock_job_manager.get_job.return_value = None
        mock_job_manager.fail_job.side_effect = JobNotFoundException("Job not found")
        
        with pytest.raises(HTTPException) as exc_info:
            await fail_job_route("nonexistent", "Error")
        
        assert exc_info.value.status_code == 404


class TestShutdownClusterRoute:
    """Tests for shutdown_cluster_route"""

    @pytest.mark.asyncio
    async def test_shutdown_cluster(self, mock_logger, mock_node_manager):
        """Test shutdown cluster route when orchestrator not available"""
        from scheduler.api.routes import shutdown_cluster_route
        from scheduler.head import Orchestrator
        from unittest.mock import patch, create_autospec
        from fastapi import BackgroundTasks

        mock_node_manager.get_connected_nodes.return_value = []
        mock_background_tasks = create_autospec(BackgroundTasks, instance=True, spec_set=True)

        # Mock orchestrator instance as None
        with patch.object(Orchestrator, '_instance', None):
            with pytest.raises(HTTPException) as exc_info:
                await shutdown_cluster_route(background_tasks=mock_background_tasks)

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_shutdown_cluster_success(self, mock_logger, mock_node_manager):
        """Test successful cluster shutdown"""
        from scheduler.api.routes import shutdown_cluster_route
        from scheduler.head import Orchestrator
        from unittest.mock import patch, create_autospec, Mock
        from fastapi import BackgroundTasks

        mock_node_manager.get_connected_nodes.return_value = [
            create_autospec(Node, instance=True, spec_set=True),
            create_autospec(Node, instance=True, spec_set=True)
        ]
        mock_background_tasks = create_autospec(BackgroundTasks, instance=True, spec_set=True)
        
        # Use create_autospec for Orchestrator (internal class)
        mock_orchestrator = create_autospec(Orchestrator, instance=True, spec_set=True)
        mock_orchestrator.shutdown_cluster_workers.return_value = True

        with patch.object(Orchestrator, '_instance', mock_orchestrator):
            result = await shutdown_cluster_route(background_tasks=mock_background_tasks)

            assert result['status'] == "shutdown_complete"
            assert result['nodes_count'] == 2
            assert result['all_confirmed'] == True
            mock_orchestrator.shutdown_cluster_workers.assert_called_once()
            mock_background_tasks.add_task.assert_called_once_with(mock_orchestrator.stop)


class TestPurgeJobRoute:
    """Tests for purge_job_route"""

    @pytest.mark.asyncio
    async def test_purge_job_success(self, mock_job_manager):
        """Test successful job purge"""
        result = await purge_job_route("job_123")

        assert result['status'] == "purge_initiated"
        assert result['job_id'] == "job_123"
        mock_job_manager.purge_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    async def test_purge_job_not_found(self, mock_job_manager):
        """Test purging non-existent job"""
        from scheduler.core.exceptions import JobNotFoundException

        mock_job_manager.purge_job.side_effect = JobNotFoundException("Job not found")

        with pytest.raises(HTTPException) as exc_info:
            await purge_job_route("nonexistent")

        assert exc_info.value.status_code == 404


class TestPurgeJobsRoute:
    """Tests for purge_jobs_route (bulk purge)"""

    @pytest.mark.asyncio
    async def test_purge_jobs_with_status_filter(self, mock_job_manager):
        """Test bulk purge with status filter"""
        mock_job_manager.purge_jobs_by_criteria.return_value = 5

        result = await purge_jobs_route({"status_filter": ["completed", "failed"]})

        assert result['purged_count'] == 5
        mock_job_manager.purge_jobs_by_criteria.assert_called_once()

    @pytest.mark.asyncio
    async def test_purge_jobs_with_time_filter(self, mock_job_manager):
        """Test bulk purge with time filter"""
        from datetime import datetime

        mock_job_manager.purge_jobs_by_criteria.return_value = 3

        before_time = datetime.now().isoformat()
        result = await purge_jobs_route({"before_time": before_time})

        assert result['purged_count'] == 3

    @pytest.mark.asyncio
    async def test_purge_jobs_no_filters(self, mock_job_manager):
        """Test bulk purge with no filters (defaults)"""
        mock_job_manager.purge_jobs_by_criteria.return_value = 10

        result = await purge_jobs_route({})

        assert result['purged_count'] == 10


class TestFreezeGPURoute:
    """Tests for freeze_gpu_route"""

    @pytest.mark.asyncio
    async def test_freeze_gpu_success(self, mock_node_manager):
        """Test freezing a GPU successfully"""
        from datetime import datetime, timedelta
        
        # Create mock node with GPUs
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_gpu = create_autospec(GPU, instance=True, spec_set=True)
        mock_gpu.frozen_until = datetime.now() + timedelta(seconds=3600)
        mock_node.gpus = [mock_gpu]
        mock_node_manager.get_node.return_value = mock_node

        result = await freeze_gpu_route("node1", 0, GPUFreezeRequest(duration_seconds=3600))

        assert result['status'] == "frozen"
        assert result['node_name'] == "node1"
        assert result['gpu_id'] == 0
        assert 'frozen_until' in result
        mock_gpu.freeze.assert_called_once_with(3600)
        mock_node_manager.save_node.assert_called_once_with(mock_node)

    @pytest.mark.asyncio
    async def test_freeze_gpu_node_not_found(self, mock_node_manager):
        """Test freezing GPU on non-existent node"""
        mock_node_manager.get_node.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await freeze_gpu_route("nonexistent", 0, GPUFreezeRequest(duration_seconds=3600))

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_freeze_gpu_invalid_gpu_id(self, mock_node_manager):
        """Test freezing with invalid GPU ID"""
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_node.gpus = [create_autospec(GPU, instance=True, spec_set=True)]  # Only 1 GPU (ID 0)
        mock_node_manager.get_node.return_value = mock_node

        with pytest.raises(HTTPException) as exc_info:
            await freeze_gpu_route("node1", 999, GPUFreezeRequest(duration_seconds=3600))

        assert exc_info.value.status_code == 400


class TestUnfreezeGPURoute:
    """Tests for unfreeze_gpu_route"""

    @pytest.mark.asyncio
    async def test_unfreeze_gpu_success(self, mock_node_manager):
        """Test unfreezing a GPU successfully"""
        mock_node = create_autospec(Node, instance=True, spec_set=True)
        mock_gpu = create_autospec(GPU, instance=True, spec_set=True)
        mock_node.gpus = [mock_gpu]
        mock_node_manager.get_node.return_value = mock_node

        result = await unfreeze_gpu_route("node1", 0)

        assert result['status'] == "unfrozen"
        assert result['node_name'] == "node1"
        assert result['gpu_id'] == 0
        mock_gpu.unfreeze.assert_called_once()
        mock_node_manager.save_node.assert_called_once_with(mock_node)

    @pytest.mark.asyncio
    async def test_unfreeze_gpu_node_not_found(self, mock_node_manager):
        """Test unfreezing GPU on non-existent node"""
        mock_node_manager.get_node.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await unfreeze_gpu_route("nonexistent", 0)

        assert exc_info.value.status_code == 404


class TestUnfreezeAllGPUsRoute:
    """Tests for unfreeze_all_gpus_route"""

    @pytest.mark.asyncio
    async def test_unfreeze_all_gpus_success(self, mock_node_manager):
        """Test unfreezing all GPUs"""
        # Create 2 nodes with frozen GPUs
        mock_gpu1 = create_autospec(GPU, instance=True, spec_set=True)
        mock_gpu1.is_frozen.return_value = True
        mock_gpu2 = create_autospec(GPU, instance=True, spec_set=True)
        mock_gpu2.is_frozen.return_value = True
        mock_gpu3 = create_autospec(GPU, instance=True, spec_set=True)
        mock_gpu3.is_frozen.return_value = False  # Not frozen

        mock_node1 = create_autospec(Node, instance=True, spec_set=True)
        mock_node1.gpus = [mock_gpu1, mock_gpu2]
        mock_node2 = create_autospec(Node, instance=True, spec_set=True)
        mock_node2.gpus = [mock_gpu3]
        
        mock_node_manager.list_nodes.return_value = [mock_node1, mock_node2]

        result = await unfreeze_all_gpus_route()

        assert result['status'] == "unfrozen"
        assert result['unfrozen_count'] == 2  # Only 2 were frozen
        mock_gpu1.unfreeze.assert_called_once()
        mock_gpu2.unfreeze.assert_called_once()
        assert not mock_gpu3.unfreeze.called  # Not frozen, so not unfrozen

