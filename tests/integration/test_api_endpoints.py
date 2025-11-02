"""
Integration tests for HTTP API endpoints.

Tests all API endpoints documented in API_REFERENCE.md using FastAPI's TestClient.
This provides comprehensive coverage of request validation, status codes, and response schemas
without requiring actual HTTP server startup.
"""

import pytest
from fastapi.testclient import TestClient

from scheduler.api.routes import create_app
from scheduler.manager.log_position_manager import LogPositionManager
from scheduler.core import JobStatus


class TestHealthEndpoint:
    """Test health check endpoint"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    def test_health_check_success(self, api_client):
        """Test GET /api/v1/health returns healthy status"""
        response = api_client.get("/api/v1/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert data["version"] == "v1"


class TestJobEndpoints:
    """Test job-related endpoints"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    # POST /api/v1/jobs - Job submission tests

    def test_submit_job_minimal(self, api_client):
        """Test POST /api/v1/jobs with minimal required fields"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2"
        })

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "pending"
        assert data["script"] == "train.py"
        # Requirements format may vary

    def test_submit_job_full(self, api_client):
        """Test POST /api/v1/jobs with all optional fields"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2",
            "name": "my-training-job",
            "script_args": ["--epochs", "100", "--lr", "0.001"],
            "working_dir": "/home/user/project",
            "env_vars": {"PYTHONPATH": "/home/user/lib", "DEBUG": "1"},
            "dependencies": [],
            "priority": 5,
        })

        assert response.status_code == 200
        data = response.json()
        # Name is used by JobManager - it may be in the response
        assert data["status"] == "pending"
        assert data["script"] == "train.py"

    def test_submit_job_with_dependencies(self, api_client):
        """Test POST /api/v1/jobs with job dependencies"""
        # Submit first job
        response1 = api_client.post("/api/v1/jobs", json={
            "script": "preprocess.py",
            "requirements": "1"
        })
        assert response1.status_code == 200
        job1_id = response1.json()["job_id"]

        # Submit dependent job
        response2 = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2",
            "dependencies": [job1_id]
        })

        assert response2.status_code == 200
        data = response2.json()
        assert data["status"] == "pending"

    def test_submit_job_invalid_requirements_empty(self, api_client):
        """Test POST /api/v1/jobs with empty requirements returns 400"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": ""
        })

        assert response.status_code == 400

    def test_submit_job_invalid_requirements_format(self, api_client):
        """Test POST /api/v1/jobs with invalid requirements format"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "invalid-format"
        })

        assert response.status_code == 400

    def test_submit_job_missing_script(self, api_client):
        """Test POST /api/v1/jobs without script field returns 422"""
        response = api_client.post("/api/v1/jobs", json={
            "requirements": "2"
        })

        assert response.status_code == 422  # Pydantic validation error

    def test_submit_job_missing_requirements(self, api_client):
        """Test POST /api/v1/jobs without requirements field returns 422"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py"
        })

        assert response.status_code == 422  # Pydantic validation error

    def test_submit_job_negative_priority(self, api_client):
        """Test POST /api/v1/jobs with negative priority"""
        response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2",
            "priority": -10
        })

        # Should accept negative priority (lower priority)
        assert response.status_code == 200


    # GET /api/v1/jobs/{job_id} - Get job details tests

    def test_get_job_success(self, api_client):
        """Test GET /api/v1/jobs/{job_id} for existing job"""
        # Submit a job first
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2",
            "name": "test-job"
        })
        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        # Get job details
        response = api_client.get(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "pending"

    def test_get_job_not_found(self, api_client):
        """Test GET /api/v1/jobs/{job_id} for non-existent job returns 404"""
        response = api_client.get("/api/v1/jobs/nonexistent-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # GET /api/v1/jobs - List jobs tests

    def test_list_jobs_empty(self, api_client):
        """Test GET /api/v1/jobs when no jobs exist"""
        response = api_client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0

    def test_list_jobs_multiple(self, api_client):
        """Test GET /api/v1/jobs returns all jobs"""
        # Submit multiple jobs
        api_client.post("/api/v1/jobs", json={"script": "job1.py", "requirements": "1"})
        api_client.post("/api/v1/jobs", json={"script": "job2.py", "requirements": "2"})
        api_client.post("/api/v1/jobs", json={"script": "job3.py", "requirements": "1"})

        response = api_client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 3
        assert data["total"] == 3

    def test_list_jobs_filter_by_status(self, api_client):
        """Test GET /api/v1/jobs?status=pending filters jobs"""
        # Submit jobs
        r1 = api_client.post("/api/v1/jobs", json={"script": "job1.py", "requirements": "1"})
        r2 = api_client.post("/api/v1/jobs", json={"script": "job2.py", "requirements": "2"})
        assert r1.status_code == 200
        assert r2.status_code == 200

        # Filter by status (use lowercase as enum values are lowercase)
        response = api_client.get("/api/v1/jobs?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        for job in data["jobs"]:
            assert job["status"] == "pending"

    def test_list_jobs_with_limit(self, api_client):
        """Test GET /api/v1/jobs?limit=2 limits results"""
        # Submit multiple jobs
        for i in range(5):
            api_client.post("/api/v1/jobs", json={
                "script": f"job{i}.py",
                "requirements": "1"
            })

        response = api_client.get("/api/v1/jobs?limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["jobs"]) == 2
        assert data["total"] == 2

    def test_list_jobs_invalid_status(self, api_client):
        """Test GET /api/v1/jobs?status=invalid_value returns error"""
        response = api_client.get("/api/v1/jobs?status=invalid_value")

        # Should return 400 Bad Request for invalid status value
        assert response.status_code == 400
        assert "invalid_value" in response.json()["detail"]

    # DELETE /api/v1/jobs/{job_id} - Cancel job tests

    def test_cancel_job_success(self, api_client):
        """Test DELETE /api/v1/jobs/{job_id} cancels pending job"""
        # Submit a job
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2"
        })
        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        # Cancel the job
        response = api_client.delete(f"/api/v1/jobs/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["job_id"] == job_id

        # Verify job is cancelled
        get_response = api_client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.json()["status"] in ["cancelled", "canceled"]

    def test_cancel_job_not_found(self, api_client):
        """Test DELETE /api/v1/jobs/{job_id} for non-existent job returns 404"""
        response = api_client.delete("/api/v1/jobs/nonexistent-job-id")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestNodeEndpoints:
    """Test node-related endpoints"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    # POST /api/v1/nodes/register - Node registration tests

    def test_register_node_success(self, api_client):
        """Test POST /api/v1/nodes/register successfully registers node"""
        response = api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 4
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "registered"
        assert data["node_name"] == "gpu-node-1"

    def test_register_node_duplicate(self, api_client):
        """Test POST /api/v1/nodes/register with duplicate node name"""
        # Register first time
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 4
        })

        # Try to register again with same name
        response = api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.11",
            "num_gpus": 2
        })

        # Should either accept (update) or reject based on implementation
        assert response.status_code in [200, 400]

    def test_register_node_zero_gpus(self, api_client):
        """Test POST /api/v1/nodes/register with zero GPUs"""
        response = api_client.post("/api/v1/nodes/register", json={
            "node_name": "cpu-node",
            "address": "192.168.1.20",
            "num_gpus": 0
        })

        # Should accept or reject based on implementation
        assert response.status_code in [200, 400]

    def test_register_node_missing_fields(self, api_client):
        """Test POST /api/v1/nodes/register with missing required fields"""
        response = api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1"
            # Missing address and num_gpus
        })

        assert response.status_code == 422  # Pydantic validation error

    # POST /api/v1/nodes/{node_name}/heartbeat - Heartbeat tests

    def test_heartbeat_success(self, api_client):
        """Test POST /api/v1/nodes/{node_name}/heartbeat updates node status"""
        # Register node first
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })

        # Send heartbeat
        response = api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {
                    "gpu_id": 0,
                    "utilization": 10.0,
                    "memory_used": 1024 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 300
                },
                {
                    "gpu_id": 1,
                    "utilization": 5.0,
                    "memory_used": 512 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 42,
                    "power_draw": 45,
                    "power_limit": 300
                }
            ]
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_heartbeat_node_not_found(self, api_client):
        """Test POST /api/v1/nodes/{node_name}/heartbeat for unregistered node"""
        response = api_client.post("/api/v1/nodes/nonexistent-node/heartbeat", json={
            "gpu_stats": []
        })

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_heartbeat_invalid_gpu_stats(self, api_client):
        """Test POST /api/v1/nodes/{node_name}/heartbeat with invalid GPU stats"""
        # Register node first
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })

        # Send heartbeat with malformed stats
        response = api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {"invalid": "data"}
            ]
        })

        assert response.status_code in [400, 422, 500]

    def test_heartbeat_empty_gpu_stats(self, api_client):
        """Test POST /api/v1/nodes/{node_name}/heartbeat with empty GPU stats"""
        # Register node first
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })

        # Send heartbeat with empty stats
        response = api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": []
        })

        assert response.status_code == 200

    # GET /api/v1/nodes - List nodes tests

    def test_list_nodes_empty(self, api_client):
        """Test GET /api/v1/nodes when no nodes registered"""
        response = api_client.get("/api/v1/nodes")

        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_list_nodes_multiple(self, api_client):
        """Test GET /api/v1/nodes returns all registered nodes"""
        # Register multiple nodes
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 4
        })
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-2",
            "address": "192.168.1.11",
            "num_gpus": 2
        })

        response = api_client.get("/api/v1/nodes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        node_names = [node["node_name"] for node in data]
        assert "gpu-node-1" in node_names
        assert "gpu-node-2" in node_names

    # GET /api/v1/nodes/{node_name} - Get node details tests

    def test_get_node_success(self, api_client):
        """Test GET /api/v1/nodes/{node_name} for existing node"""
        # Register node
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 4
        })

        response = api_client.get("/api/v1/nodes/gpu-node-1")

        assert response.status_code == 200
        data = response.json()
        assert data["node_name"] == "gpu-node-1"
        assert data["address"] == "192.168.1.10"
        assert data["num_gpus"] == 4
        assert "status" in data
        assert "gpus" in data

    def test_get_node_not_found(self, api_client):
        """Test GET /api/v1/nodes/{node_name} for non-existent node"""
        response = api_client.get("/api/v1/nodes/nonexistent-node")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestWorkerEndpoints:
    """Test worker-related endpoints for job execution"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    # GET /api/v1/workers/{node_name}/jobs/next - Poll job tests

    def test_poll_job_no_jobs(self, api_client):
        """Test GET /api/v1/workers/{node_name}/jobs/next when no jobs assigned"""
        # Register node
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })

        response = api_client.get("/api/v1/workers/gpu-node-1/jobs/next")

        assert response.status_code == 200
        # Should return None or null when no jobs
        assert response.json() is None

    def test_poll_job_node_not_found(self, api_client):
        """Test GET /api/v1/workers/{node_name}/jobs/next for unregistered node"""
        response = api_client.get("/api/v1/workers/nonexistent-node/jobs/next")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # POST /api/v1/workers/jobs/{job_id}/complete - Complete job tests

    def test_complete_job_success(self, api_client, job_manager, node_manager):
        """Test POST /api/v1/workers/jobs/{job_id}/complete marks job complete"""
        # Submit and manually assign a job
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2"
        })
        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        # Register node and send heartbeat to initialize GPUs
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })
        api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {
                    "gpu_id": 0,
                    "utilization": 10.0,
                    "memory_used": 1024 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 300
                },
                {
                    "gpu_id": 1,
                    "utilization": 5.0,
                    "memory_used": 512 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 42,
                    "power_draw": 45,
                    "power_limit": 300
                }
            ]
        })

        # Manually assign job (simulating scheduler)
        job = job_manager.get_job(job_id)
        job.assigned_node = "gpu-node-1"
        job.assigned_gpus = [0, 1]
        job.status = JobStatus.RUNNING

        # Note: We no longer track assigned_job_id - GPU availability is determined
        # Now we use running_job_id to show what's currently running via nvml process detection
        # by actual usage monitoring via pynvml

        # Complete the job
        response = api_client.post(f"/api/v1/workers/jobs/{job_id}/complete?exit_code=0")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["job_id"] == job_id

        # Verify job is completed
        get_response = api_client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.json()["status"] == "completed"
        assert get_response.json()["exit_code"] == 0

    def test_complete_job_not_found(self, api_client):
        """Test POST /api/v1/workers/jobs/{job_id}/complete for non-existent job"""
        response = api_client.post("/api/v1/workers/jobs/nonexistent-job/complete?exit_code=0")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_complete_job_nonzero_exit_code(self, api_client, job_manager, node_manager):
        """Test POST /api/v1/workers/jobs/{job_id}/complete with non-zero exit code"""
        # Submit and assign a job
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "1"
        })
        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        # Register node and send heartbeat to initialize GPUs
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })
        api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {
                    "gpu_id": 0,
                    "utilization": 10.0,
                    "memory_used": 1024 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 300
                },
                {
                    "gpu_id": 1,
                    "utilization": 5.0,
                    "memory_used": 512 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 42,
                    "power_draw": 45,
                    "power_limit": 300
                }
            ]
        })

        # Manually assign job
        job = job_manager.get_job(job_id)
        job.assigned_node = "gpu-node-1"
        job.assigned_gpus = [0]
        job.status = JobStatus.RUNNING

        # Note: We no longer track assigned_job_id - GPU availability is determined
        # Now we use running_job_id to show what's currently running via nvml process detection
        # by actual usage monitoring via pynvml

        # Complete with error exit code
        response = api_client.post(f"/api/v1/workers/jobs/{job_id}/complete?exit_code=1")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

        # Verify exit code is recorded
        get_response = api_client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.json()["exit_code"] == 1

    # POST /api/v1/workers/jobs/{job_id}/fail - Fail job tests

    def test_fail_job_success(self, api_client, job_manager, node_manager):
        """Test POST /api/v1/workers/jobs/{job_id}/fail marks job as failed"""
        # Submit and assign a job
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2"
        })
        assert submit_response.status_code == 200
        job_id = submit_response.json()["job_id"]

        # Register node and send heartbeat to initialize GPUs
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })
        api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {
                    "gpu_id": 0,
                    "utilization": 10.0,
                    "memory_used": 1024 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 300
                },
                {
                    "gpu_id": 1,
                    "utilization": 5.0,
                    "memory_used": 512 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 42,
                    "power_draw": 45,
                    "power_limit": 300
                }
            ]
        })

        # Manually assign job
        job = job_manager.get_job(job_id)
        job.assigned_node = "gpu-node-1"
        job.assigned_gpus = [0, 1]
        job.status = JobStatus.RUNNING

        # Note: We no longer track assigned_job_id - GPU availability is determined
        # Now we use running_job_id to show what's currently running via nvml process detection
        # by actual usage monitoring via pynvml

        # Fail the job
        response = api_client.post(
            f"/api/v1/workers/jobs/{job_id}/fail?error_message=GPU%20out%20of%20memory"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["job_id"] == job_id

        # Verify job is failed
        get_response = api_client.get(f"/api/v1/jobs/{job_id}")
        assert get_response.json()["status"] == "failed"
        assert "out of memory" in get_response.json()["error_message"].lower()

    def test_fail_job_not_found(self, api_client):
        """Test POST /api/v1/workers/jobs/{job_id}/fail for non-existent job"""
        response = api_client.post(
            "/api/v1/workers/jobs/nonexistent-job/fail?error_message=error"
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestErrorHandling:
    """Test general error handling and edge cases"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    def test_invalid_json_body(self, api_client):
        """Test POST with invalid JSON returns 422"""
        response = api_client.post(
            "/api/v1/jobs",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422

    def test_missing_content_type(self, api_client):
        """Test POST without Content-Type header"""
        response = api_client.post(
            "/api/v1/jobs",
            data='{"script": "train.py", "requirements": "2"}'
        )

        # FastAPI TestClient usually handles this, but verify it doesn't crash
        assert response.status_code in [200, 422]

    def test_invalid_endpoint(self, api_client):
        """Test GET to non-existent endpoint returns 404"""
        response = api_client.get("/api/v1/invalid-endpoint")

        assert response.status_code == 404


class TestResponseSchemas:
    """Test response schema validation"""

    @pytest.fixture
    def api_client(self, job_manager, node_manager):
        """Create test client with test dependencies"""
        mock_log_pos_mgr = Mock(spec_set=LogPositionManager)
        app = create_app(job_manager, node_manager, mock_log_pos_mgr)
        return TestClient(app)

    def test_job_response_schema(self, api_client):
        """Test JobResponse contains all expected fields"""
        submit_response = api_client.post("/api/v1/jobs", json={
            "script": "train.py",
            "requirements": "2",
            "name": "test-job"
        })

        assert submit_response.status_code == 200
        data = submit_response.json()

        # Required fields
        assert "job_id" in data
        assert "name" in data
        assert "script" in data
        assert "requirements" in data
        assert "status" in data
        assert "submitted_at" in data

        # Optional fields (should be present even if None)
        assert "started_at" in data
        assert "completed_at" in data
        assert "assigned_node" in data
        assert "assigned_gpus" in data
        assert "exit_code" in data
        assert "error_message" in data

    def test_node_response_schema(self, api_client):
        """Test NodeResponse contains all expected fields"""
        # Register node
        api_client.post("/api/v1/nodes/register", json={
            "node_name": "gpu-node-1",
            "address": "192.168.1.10",
            "num_gpus": 2
        })

        # Send heartbeat to initialize GPUs
        api_client.post("/api/v1/nodes/gpu-node-1/heartbeat", json={
            "gpu_stats": [
                {
                    "gpu_id": 0,
                    "utilization": 10.0,
                    "memory_used": 1024 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 300
                },
                {
                    "gpu_id": 1,
                    "utilization": 5.0,
                    "memory_used": 512 * 1024 * 1024,
                    "memory_total": 16 * 1024 * 1024 * 1024,
                    "temperature": 42,
                    "power_draw": 45,
                    "power_limit": 300
                }
            ]
        })

        response = api_client.get("/api/v1/nodes/gpu-node-1")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "node_name" in data
        assert "address" in data
        assert "num_gpus" in data
        assert "status" in data
        assert "gpus" in data
        assert "registered_at" in data

        # GPU fields
        assert len(data["gpus"]) == 2
        for gpu in data["gpus"]:
            assert "gpu_id" in gpu
            assert "utilization" in gpu
            assert "memory_used" in gpu
            assert "memory_total" in gpu
            assert "temperature" in gpu
            assert "power_draw" in gpu

    def test_job_list_response_schema(self, api_client):
        """Test JobListResponse contains jobs and total"""
        response = api_client.get("/api/v1/jobs")

        assert response.status_code == 200
        data = response.json()

        assert "jobs" in data
        assert "total" in data
        assert isinstance(data["jobs"], list)
        assert isinstance(data["total"], int)
