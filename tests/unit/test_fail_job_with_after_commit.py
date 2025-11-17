"""
Unit tests to ensure fail_job API correctly handles after_commit_ref parameter.

This test was added to catch a bug where after_commit_ref was passed in the wrong
position, causing git commit SHAs to be stored in the exit_code field.
"""
import pytest
from unittest.mock import create_autospec, patch
from scheduler.core import Job, Node, JobStatus
from scheduler.core.exceptions import JobNotFoundException
from fastapi import HTTPException


@pytest.fixture
def mock_job_manager():
    """Create a mock job manager"""
    with patch('scheduler.api.routes._job_manager') as mock:
        yield mock


@pytest.fixture
def mock_node_manager():
    """Create a mock node manager"""
    with patch('scheduler.api.routes._node_manager') as mock:
        yield mock


class TestFailJobWithAfterCommitRef:
    """Test fail_job API route with after_commit_ref parameter"""

    @pytest.mark.asyncio
    async def test_fail_job_with_exit_code_only(self, mock_job_manager, mock_node_manager):
        """Test failing a job with exit_code only"""
        from scheduler.api.routes import fail_job_route

        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        result = await fail_job_route("job_123", "Error occurred", exit_code=2)

        assert result['status'] == "failed"
        # Verify exit_code is passed in the correct position
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred", 2, None)

    @pytest.mark.asyncio
    async def test_fail_job_with_after_commit_ref_only(self, mock_job_manager, mock_node_manager):
        """Test failing a job with after_commit_ref only (regression test for the bug)"""
        from scheduler.api.routes import fail_job_route

        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        # This is the critical test - after_commit_ref should NOT be passed as exit_code
        git_sha = "7110dc301eddfbafefe6bd83a4fbe666b2c9d6ec"
        result = await fail_job_route("job_123", "Error occurred", after_commit_ref=git_sha)

        assert result['status'] == "failed"
        # Verify after_commit_ref is passed in the correct position (4th param, not 3rd)
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred", None, git_sha)

    @pytest.mark.asyncio
    async def test_fail_job_with_both_exit_code_and_after_commit_ref(self, mock_job_manager, mock_node_manager):
        """Test failing a job with both exit_code and after_commit_ref"""
        from scheduler.api.routes import fail_job_route

        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        git_sha = "7110dc301eddfbafefe6bd83a4fbe666b2c9d6ec"
        result = await fail_job_route("job_123", "Error occurred", exit_code=2, after_commit_ref=git_sha)

        assert result['status'] == "failed"
        # Verify both parameters are passed correctly
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred", 2, git_sha)

    @pytest.mark.asyncio
    async def test_fail_job_with_neither_exit_code_nor_after_commit_ref(self, mock_job_manager, mock_node_manager):
        """Test failing a job with only error message (original test case)"""
        from scheduler.api.routes import fail_job_route

        mock_job = create_autospec(Job, instance=True, spec_set=True)
        mock_job.assigned_node = "node1"
        mock_job_manager.get_job.return_value = mock_job
        mock_node_manager.get_node.return_value = create_autospec(Node, instance=True, spec_set=True)
        
        result = await fail_job_route("job_123", "Error occurred")

        assert result['status'] == "failed"
        # Verify both optional parameters are None
        mock_job_manager.fail_job.assert_called_once_with("job_123", "Error occurred", None, None)


class TestJobResponseWithAfterCommitRef:
    """Test JobResponse serialization includes after_commit_ref"""

    def test_job_response_includes_after_commit_ref(self):
        """Test that JobResponse schema includes after_commit_ref field"""
        from scheduler.api.schemas import JobResponse
        from scheduler.core import JobRequirement
        from datetime import datetime

        # Create a job with after_commit_ref set
        job = Job(
            job_id="job_123",
            name="test-job",
            command=["python", "test.py"],
            requirements=JobRequirement("2"),
            working_dir="/tmp",
            status=JobStatus.FAILED,
            exit_code=2,
            error_message="Test error",
            after_commit_ref="7110dc301eddfbafefe6bd83a4fbe666b2c9d6ec",
            submitted_at=datetime.now()
        )

        # This should not raise a ValidationError
        response = JobResponse.from_job(job)

        assert response.exit_code == 2
        assert response.after_commit_ref == "7110dc301eddfbafefe6bd83a4fbe666b2c9d6ec"
        assert response.error_message == "Test error"

    def test_job_response_validates_exit_code_type(self):
        """Test that JobResponse rejects string values for exit_code"""
        from scheduler.api.schemas import JobResponse
        from pydantic import ValidationError

        # This should raise a ValidationError because exit_code must be int or None
        with pytest.raises(ValidationError) as exc_info:
            JobResponse(
                job_id="job_123",
                name="test-job",
                command=["python", "test.py"],
                requirements="2",
                status="failed",
                submitted_at="2025-11-16T00:00:00",
                exit_code="7110dc301eddfbafefe6bd83a4fbe666b2c9d6ec",  # WRONG: string instead of int
                error_message="Test error"
            )
        
        # Verify the error is about exit_code type
        errors = exc_info.value.errors()
        assert any(error['loc'] == ('exit_code',) for error in errors)
