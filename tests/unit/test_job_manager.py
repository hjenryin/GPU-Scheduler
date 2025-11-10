"""Unit tests for JobManager"""
import pytest
from datetime import datetime

from scheduler.core.models import Job, JobStatus, JobRequirement
from scheduler.core.exceptions import JobNotFoundException
from scheduler.manager import JobManager
from scheduler.manager import PersistenceManager


@pytest.fixture
def persistence_manager(temp_dir, test_config):
    """Create persistence manager for testing"""
    from scheduler.storage import FileBackend
    backend = FileBackend(storage_dir=temp_dir)
    return PersistenceManager(backend=backend, config=test_config)


@pytest.fixture
def job_manager(persistence_manager, test_config):
    """Create job manager for testing"""
    return JobManager(persistence=persistence_manager, config=test_config)


class TestJobManager:
    """Tests for JobManager class"""

    def test_submit_job_minimal(self, job_manager):
        """Test submitting job with minimal parameters"""
        job = job_manager.submit_job(
            script="/path/to/script.py",
            requirements="2"
        )

        assert job.job_id is not None
        assert job.name == "script.py"
        assert job.script == "/path/to/script.py"
        assert job.status == JobStatus.PENDING
        assert job.submitted_at is not None

    def test_submit_job_full_params(self, job_manager):
        """Test submitting job with all parameters"""
        job = job_manager.submit_job(
            script="/path/to/script.py",
            requirements="gpu1:4",
            name="my-job",
            script_args=["--epochs", "100"],
            working_dir="/home/user",
            env_vars={"KEY": "value"},
            dependencies=["job-000"],
            priority=5,
        )

        assert job.name == "my-job"
        assert job.script_args == ["--epochs", "100"]
        assert job.working_dir == "/home/user"
        assert job.env_vars == {"KEY": "value"}
        assert job.dependencies == ["job-000"]
        assert job.priority == 5

    def test_submit_job_invalid_requirements(self, job_manager):
        """Test submitting job with invalid requirements raises exception"""
        from scheduler.core.exceptions import InvalidRequirementException

        with pytest.raises(InvalidRequirementException):
            job_manager.submit_job(
                script="/script.py",
                requirements="invalid"
            )

    def test_get_job_not_found(self, job_manager):
        """Test getting non-existent job returns None"""
        job = job_manager.get_job("nonexistent")
        assert job is None

    def test_list_jobs(self, job_manager):
        """Test listing all jobs"""
        job1 = job_manager.submit_job("/script1.py", "2")
        job2 = job_manager.submit_job("/script2.py", "1")

        all_jobs = job_manager.list_jobs()

        assert len(all_jobs) == 2
        job_ids = [j.job_id for j in all_jobs]
        assert job1.job_id in job_ids
        assert job2.job_id in job_ids

    def test_get_pending_jobs(self, job_manager):
        """Test getting pending jobs sorted by priority"""
        job_low = job_manager.submit_job("/script1.py", "2", priority=1)
        job_high = job_manager.submit_job("/script2.py", "2", priority=10)
        job_med = job_manager.submit_job("/script3.py", "2", priority=5)

        # Start one job
        job_manager.start_job(job_low.job_id, "gpu1", [0, 1])

        pending = job_manager.get_pending_jobs()

        assert len(pending) == 2
        # Should be sorted by priority (high to low)
        assert pending[0].job_id == job_high.job_id
        assert pending[1].job_id == job_med.job_id

    def test_get_running_jobs(self, job_manager):
        """Test getting running jobs"""
        job1 = job_manager.submit_job("/script1.py", "2")
        job2 = job_manager.submit_job("/script2.py", "2")

        # Start job1
        job_manager.start_job(job1.job_id, "gpu1", [0, 1])

        running = job_manager.get_running_jobs()

        assert len(running) == 1
        assert running[0].job_id == job1.job_id

    def test_get_completed_job_ids(self, job_manager):
        """Test getting completed job IDs"""
        job1 = job_manager.submit_job("/script1.py", "2")
        job2 = job_manager.submit_job("/script2.py", "2")

        # Complete job1
        job_manager.start_job(job1.job_id, "gpu1", [0, 1])
        job_manager.complete_job(job1.job_id, exit_code=0)

        completed_ids = job_manager.get_completed_job_ids()

        assert len(completed_ids) == 1
        assert job1.job_id in completed_ids

    def test_start_job(self, job_manager):
        """Test starting a job"""
        job = job_manager.submit_job("/script.py", "2")

        job_manager.start_job(job.job_id, "gpu1", [0, 1])

        updated = job_manager.get_job(job.job_id)
        assert updated.status == JobStatus.RUNNING
        assert updated.assigned_node == "gpu1"
        assert updated.assigned_gpus == [0, 1]
        assert updated.started_at is not None

    def test_complete_job(self, job_manager):
        """Test completing a job"""
        job = job_manager.submit_job("/script.py", "2")
        job_manager.start_job(job.job_id, "gpu1", [0, 1])

        job_manager.complete_job(job.job_id, exit_code=0)

        updated = job_manager.get_job(job.job_id)
        assert updated.status == JobStatus.COMPLETED
        assert updated.exit_code == 0
        assert updated.completed_at is not None

    def test_fail_job(self, job_manager):
        """Test failing a job"""
        job = job_manager.submit_job("/script.py", "2")
        job_manager.start_job(job.job_id, "gpu1", [0, 1])

        job_manager.fail_job(job.job_id, error_message="Out of memory")

        updated = job_manager.get_job(job.job_id)
        assert updated.status == JobStatus.FAILED
        assert updated.error_message == "Out of memory"
        assert updated.completed_at is not None

    def test_cancel_job_pending(self, job_manager):
        """Test canceling a pending job"""
        job = job_manager.submit_job("/script.py", "2")

        job_manager.cancel_job(job.job_id)

        updated = job_manager.get_job(job.job_id)
        assert updated.status == JobStatus.CANCELLED

    def test_cancel_job_running(self, job_manager):
        """Test canceling a running job"""
        job = job_manager.submit_job("/script.py", "2")
        job_manager.start_job(job.job_id, "gpu1", [0, 1])

        job_manager.cancel_job(job.job_id)

        updated = job_manager.get_job(job.job_id)
        assert updated.status == JobStatus.CANCELLED

    def test_list_jobs_by_status(self, job_manager):
        """Test filtering jobs by status using list_jobs"""
        job1 = job_manager.submit_job("/script1.py", "2")
        job2 = job_manager.submit_job("/script2.py", "2")
        job3 = job_manager.submit_job("/script3.py", "2")

        job_manager.start_job(job1.job_id, "gpu1", [0, 1])
        job_manager.complete_job(job1.job_id, exit_code=0)
        job_manager.start_job(job2.job_id, "gpu2", [0, 1])

        pending = job_manager.list_jobs(status_filter=JobStatus.PENDING)
        running = job_manager.list_jobs(status_filter=JobStatus.RUNNING)
        completed = job_manager.list_jobs(status_filter=JobStatus.COMPLETED)

        assert len(pending) == 1
        assert len(running) == 1
        assert len(completed) == 1

    def test_persistence_integration(self, persistence_manager, test_config):
        """Test jobs are persisted and loaded"""
        # Create first manager and add job
        manager1 = JobManager(persistence=persistence_manager, config=test_config)
        job = manager1.submit_job("/script.py", "2", name="persistent-job")
        job_id = job.job_id

        # Create second manager (simulates restart)
        manager2 = JobManager(persistence=persistence_manager, config=test_config)

        # Job should be loaded
        loaded_job = manager2.get_job(job_id)
        assert loaded_job.name == "persistent-job"
        assert loaded_job.status == JobStatus.PENDING

    def test_job_versioned_script_assignment(self, job_manager):
        """Test that versioned script path can be assigned to jobs"""
        job = job_manager.submit_job("/script.py", "2")

        # Directly update the job's versioned script path (simulating worker behavior)
        job.versioned_script_path = "/tmp/script.py.scheduler_job001_abc123.py"
        job_manager.persistence.save_job(job)

        updated = job_manager.get_job(job.job_id)
        assert updated.versioned_script_path == "/tmp/script.py.scheduler_job001_abc123.py"

    def test_list_jobs_with_limit(self, job_manager):
        """Test listing jobs with limit parameter"""
        # Submit multiple jobs
        for i in range(5):
            job_manager.submit_job(
                script=f"/path/to/script{i}.py",
                requirements="1"
            )
        
        # Test with limit
        jobs = job_manager.list_jobs(limit=3)
        assert len(jobs) == 3
        
        # Test with limit larger than total
        jobs = job_manager.list_jobs(limit=10)
        assert len(jobs) == 5

    def test_start_job_not_found(self, job_manager):
        """Test starting non-existent job"""
        with pytest.raises(JobNotFoundException):
            job_manager.start_job("non-existent", "node1", [0])

    def test_complete_job_not_found(self, job_manager):
        """Test completing non-existent job"""
        with pytest.raises(JobNotFoundException):
            job_manager.complete_job("non-existent", 0)

    def test_fail_job_not_found(self, job_manager):
        """Test failing non-existent job"""
        with pytest.raises(JobNotFoundException):
            job_manager.fail_job("non-existent", "Test error")

    def test_resolve_dependency_shorthand_single_caret(self, job_manager):
        """Test resolving ^ to most recent job"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job2 = job_manager.submit_job("/script2.py", "1")

        resolved = job_manager.resolve_dependency_shorthand("^")
        assert resolved == job2.job_id

    def test_resolve_dependency_shorthand_double_caret(self, job_manager):
        """Test resolving ^^ to second most recent job"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job2 = job_manager.submit_job("/script2.py", "1")
        job3 = job_manager.submit_job("/script3.py", "1")

        resolved = job_manager.resolve_dependency_shorthand("^^")
        assert resolved == job2.job_id

    def test_resolve_dependency_shorthand_triple_caret(self, job_manager):
        """Test resolving ^^^ to third most recent job"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job2 = job_manager.submit_job("/script2.py", "1")
        job3 = job_manager.submit_job("/script3.py", "1")
        job4 = job_manager.submit_job("/script4.py", "1")

        resolved = job_manager.resolve_dependency_shorthand("^^^")
        assert resolved == job2.job_id

    def test_resolve_dependency_shorthand_regular_job_id(self, job_manager):
        """Test that regular job IDs pass through unchanged"""
        job_id = "job_abc123"
        resolved = job_manager.resolve_dependency_shorthand(job_id)
        assert resolved == job_id

    def test_resolve_dependency_shorthand_no_jobs(self, job_manager):
        """Test error when no jobs exist to reference"""
        with pytest.raises(ValueError, match="No previous jobs to reference"):
            job_manager.resolve_dependency_shorthand("^")

    def test_resolve_dependency_shorthand_insufficient_history(self, job_manager):
        """Test error when not enough jobs exist"""
        job1 = job_manager.submit_job("/script1.py", "1")

        with pytest.raises(ValueError, match="Only 1 job available"):
            job_manager.resolve_dependency_shorthand("^^")

    def test_resolve_dependency_shorthand_invalid_syntax(self, job_manager):
        """Test error for invalid syntax like ^a"""
        with pytest.raises(ValueError, match="Invalid dependency syntax"):
            job_manager.resolve_dependency_shorthand("^a")

    def test_resolve_dependency_shorthand_excludes_failed(self, job_manager):
        """Test that FAILED jobs are excluded from ^ resolution"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job_manager.start_job(job1.job_id, "node1", [0])
        job_manager.fail_job(job1.job_id, "Test failure")

        job2 = job_manager.submit_job("/script2.py", "1")

        # ^ should resolve to job2, not job1 (which is FAILED)
        resolved = job_manager.resolve_dependency_shorthand("^")
        assert resolved == job2.job_id

    def test_resolve_dependency_shorthand_excludes_cancelled(self, job_manager):
        """Test that CANCELLED jobs are excluded from ^ resolution"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job_manager.cancel_job(job1.job_id)

        job2 = job_manager.submit_job("/script2.py", "1")

        # ^ should resolve to job2, not job1 (which is CANCELLED)
        resolved = job_manager.resolve_dependency_shorthand("^")
        assert resolved == job2.job_id

    def test_submit_job_with_caret_dependency(self, job_manager):
        """Test submitting job with ^ dependency gets resolved"""
        job1 = job_manager.submit_job("/script1.py", "1")
        job2 = job_manager.submit_job("/script2.py", "1", dependencies=["^"])

        assert job2.dependencies == [job1.job_id]

    def test_submit_job_with_mixed_dependencies(self, job_manager):
        """Test submitting job with mix of ^ and regular job IDs"""
        job1 = job_manager.submit_job("/script1.py", "1")
        explicit_job_id = "job_explicit123"

        job2 = job_manager.submit_job("/script2.py", "1", dependencies=["^", explicit_job_id])

        assert job2.dependencies == [job1.job_id, explicit_job_id]
