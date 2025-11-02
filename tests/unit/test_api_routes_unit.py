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
    stream_job_logs_route,
    register_node_route,
    heartbeat_route,
    list_nodes_route,
    get_node_route,
    poll_job_route,
    complete_job_route,
    fail_job_route,
    shutdown_cluster_route
)
from scheduler.api.schemas import JobSubmitRequest, NodeRegisterRequest, NodeHeartbeat
from scheduler.core.models import Job, JobStatus, JobRequirement, Node, NodeStatus, GPUStats
from scheduler.core.exceptions import JobNotFoundException, NodeNotFoundException


# Fixture-based mocking with autospec
@pytest.fixture
def mock_job_manager():
    """Mocks the _job_manager in the routes file with autospec."""
    # Use Mock with spec instead of autospec on already-mocked attributes
    from scheduler.manager import JobManager
    mock_jm = MagicMock(spec=JobManager)
    
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


class TestStreamJobLogsRoute:
    """Tests for stream_job_logs_route"""

    @pytest.mark.asyncio
    async def test_stream_job_logs_not_implemented(self):
        """Test that streaming logs is not yet implemented"""
        with pytest.raises(HTTPException) as exc_info:
            await stream_job_logs_route("job_123")
        
        assert exc_info.value.status_code == 501


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
        
        assert result['status'] == "registered"
        assert result['node_name'] == "node1"
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


class TestHeartbeatRoute:
    """Tests for heartbeat_route"""

    @pytest.mark.asyncio
    async def test_heartbeat_success(self, mock_node_manager):
        """Test successful heartbeat"""
        request = NodeHeartbeat(gpu_stats=[])
        
        result = await heartbeat_route("node1", request)
        
        assert result['status'] == "ok"
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
    async def test_heartbeat_returns_shutdown_flag(self, mock_node_manager):
        """Test heartbeat returns shutdown_requested flag"""
        from unittest.mock import Mock
        request = NodeHeartbeat(gpu_stats=[])
        
        # Mock node with shutdown requested
        mock_node = Mock()
        mock_node.shutdown_requested = True
        mock_node_manager.get_node.return_value = mock_node
        
        result = await heartbeat_route("node1", request)
        
        assert result['status'] == "ok"
        assert result['shutdown_requested'] == True
        mock_node_manager.update_heartbeat.assert_called_once()
        mock_node_manager.get_node.assert_called_once_with("node1")

    @pytest.mark.asyncio
    async def test_heartbeat_no_shutdown_requested(self, mock_node_manager):
        """Test heartbeat when shutdown not requested"""
        from unittest.mock import Mock
        request = NodeHeartbeat(gpu_stats=[])
        
        # Mock node without shutdown requested
        mock_node = Mock()
        mock_node.shutdown_requested = False
        mock_node_manager.get_node.return_value = mock_node
        
        result = await heartbeat_route("node1", request)
        
        assert result['status'] == "ok"
        assert result['shutdown_requested'] == False


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
        mock_node_manager.get_node.return_value = Mock()  # Need a valid node
        
        result = await poll_job_route("node1")
        
        assert result is None


class TestCompleteJobRoute:
    """Tests for complete_job_route"""

    @pytest.mark.asyncio
    async def test_complete_job_success(self, mock_job_manager, mock_node_manager):
        """Test successful job completion"""
        from scheduler.api.routes import complete_job_route
        
        # Mock both managers
        mock_job = Mock()
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = Mock()
        
        result = await complete_job_route("job_123", exit_code=0)
        
        assert result['status'] == "completed"
        mock_job_manager.complete_job.assert_called_once_with("job_123", 0)

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
        mock_job = Mock()
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = Mock()
        
        result = await fail_job_route("job_123", "Error occurred")
        
        assert result['status'] == "failed"
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred")

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
        """Test shutdown cluster route"""
        from scheduler.api.routes import shutdown_cluster_route
        from scheduler.head import Orchestrator
        from unittest.mock import patch

        mock_node_manager.get_connected_nodes.return_value = []

        # Mock orchestrator instance as None
        with patch.object(Orchestrator, '_instance', None):
            with pytest.raises(HTTPException) as exc_info:
                await shutdown_cluster_route(graceful_timeout=60, force=False)

            assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_shutdown_cluster_success(self, mock_logger, mock_node_manager):
        """Test successful cluster shutdown"""
        from scheduler.api.routes import shutdown_cluster_route
        from scheduler.head import Orchestrator
        from unittest.mock import MagicMock, patch

        mock_node_manager.get_connected_nodes.return_value = [Mock(), Mock()]
        mock_orchestrator = MagicMock()
        mock_orchestrator.request_cluster_shutdown = MagicMock()

        with patch.object(Orchestrator, '_instance', mock_orchestrator):
            result = await shutdown_cluster_route(graceful_timeout=60, force=True)

            assert result['status'] == "shutdown_initiated"
            assert result['nodes_count'] == 2
            mock_orchestrator.request_cluster_shutdown.assert_called_once_with(60, True)

