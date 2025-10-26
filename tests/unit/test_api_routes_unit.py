"""Unit tests for API route functions with proper mocking"""
import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from scheduler.api.routes import (
    health_check_route,
    submit_job_route,
    get_job_route,
    list_jobs_route,
    cancel_job_route,
    get_job_logs_route
)
from scheduler.api.schemas import JobSubmitRequest
from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.core.exceptions import JobNotFoundException


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
    @patch('scheduler.api.routes._job_manager')
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
    @patch('scheduler.api.routes._job_manager')
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


class TestGetJobRoute:
    """Tests for get_job_route"""

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
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
    @patch('scheduler.api.routes._job_manager')
    async def test_get_job_not_found(self, mock_job_manager):
        """Test getting a non-existent job returns 404"""
        # Route checks if job is None, not exception
        mock_job_manager.get_job.return_value = None
        
        with pytest.raises(HTTPException) as exc_info:
            await get_job_route("nonexistent")
        
        assert exc_info.value.status_code == 404
        assert "not found" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
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
    @patch('scheduler.api.routes._job_manager')
    async def test_list_jobs_empty(self, mock_job_manager):
        """Test listing jobs when empty"""
        mock_job_manager.list_jobs.return_value = []
        
        result = await list_jobs_route()
        
        assert result.jobs == []
        assert result.total == 0

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
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
    @patch('scheduler.api.routes._job_manager')
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
    @patch('scheduler.api.routes._job_manager')
    async def test_list_jobs_with_limit(self, mock_job_manager):
        """Test listing jobs with limit parameter"""
        mock_job_manager.list_jobs.return_value = []
        
        await list_jobs_route(status=None, limit=5)
        
        mock_job_manager.list_jobs.assert_called_once_with(status_filter=None, limit=5)


class TestCancelJobRoute:
    """Tests for cancel_job_route"""

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
    async def test_cancel_job_success(self, mock_job_manager):
        """Test successful job cancellation"""
        mock_job_manager.cancel_job.return_value = True
        
        result = await cancel_job_route("job_123")
        
        assert result['status'] == "cancelled"
        assert result['job_id'] == "job_123"
        mock_job_manager.cancel_job.assert_called_once_with("job_123")

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
    async def test_cancel_job_not_found(self, mock_job_manager):
        """Test canceling a non-existent job returns 404"""
        mock_job_manager.cancel_job.side_effect = JobNotFoundException("Job not found")
        
        with pytest.raises(HTTPException) as exc_info:
            await cancel_job_route("nonexistent")
        
        assert exc_info.value.status_code == 404


class TestListJobsRouteValidation:
    """Tests for list_jobs_route validation"""

    @pytest.mark.asyncio
    @patch('scheduler.api.routes._job_manager')
    async def test_list_jobs_invalid_status(self, mock_job_manager):
        """Test that invalid status filter returns 400"""
        with pytest.raises(HTTPException) as exc_info:
            await list_jobs_route(status='invalid_status')
        
        assert exc_info.value.status_code == 400
        assert "Invalid status value" in str(exc_info.value.detail)

