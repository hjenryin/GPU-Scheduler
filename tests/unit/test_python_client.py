"""Unit tests for Python API client (SchedulerClient)"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

from scheduler.api.client import SchedulerClient
from scheduler.core.exceptions import (
    ConnectionException,
    JobNotFoundException,
    NodeNotFoundException,
    ValidationException,
)
from scheduler.core.models import Job, JobStatus, Node, GPUStats
from scheduler.core import constants


class TestSchedulerClientInitialization:
    """Tests for client initialization"""

    def test_client_initialization_with_address(self):
        """Test client initializes with provided address"""
        with patch('scheduler.api.client.load_config') as mock_load_config:
            mock_load_config.return_value = Mock()
            client = SchedulerClient(address="test-host:9000")

            assert client.head_address == "test-host:9000"
            assert "test-host:9000" in client.base_url
            assert f"{constants.API_BASE_PATH}" in client.base_url

    def test_client_initialization_without_address(self):
        """Test client auto-detects address from config"""
        from scheduler.core.config import Config, HeadConfig

        mock_config = Config(
            address="configured-host:8888",
            head=HeadConfig(port=8888)
        )

        with patch('scheduler.api.client.load_config', return_value=mock_config):
            client = SchedulerClient()

            assert client.head_address == "configured-host:8888"
            assert "configured-host:8888" in client.base_url

    def test_client_initialization_with_custom_config(self):
        """Test client initializes with custom config"""
        from scheduler.core.config import Config, HeadConfig

        custom_config = Config(
            address="custom-host:7777",
            head=HeadConfig(port=7777)
        )

        client = SchedulerClient(config=custom_config)

        assert client.config == custom_config
        assert "custom-host:7777" in client.base_url

    def test_client_session_has_retry_strategy(self):
        """Test client session is configured with retry logic"""
        with patch('scheduler.api.client.load_config') as mock_load_config:
            mock_load_config.return_value = Mock()
            client = SchedulerClient(address="test:9000")

            assert client.session is not None
            # Verify adapters are mounted
            assert "http://" in client.session.adapters
            assert "https://" in client.session.adapters


class TestSubmitJob:
    """Tests for submit_job method"""

    @patch('scheduler.api.client.load_config')
    def test_submit_job_success(self, mock_load_config):
        """Test successful job submission"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_123",
            "name": "test_job",
            "script": "train.py",
            "requirements": "2",
            "status": "pending",
            "submitted_at": "2025-01-01T00:00:00",
            "started_at": None,
            "completed_at": None,
            "assigned_node": None,
            "assigned_gpus": None,
            "exit_code": None,
            "error_message": None,
            "script_args": ["--epochs", "10"],
            "working_dir": "/workspace",
            "env_vars": {"KEY": "value"},
            "dependencies": [],
            "priority": 0,
            "timeout": None
        }

        with patch.object(client.session, 'post', return_value=mock_response):
            job = client.submit_job(
                script="train.py",
                requirements="2",
                name="test_job",
                script_args=["--epochs", "10"],
                working_dir="/workspace",
                env_vars={"KEY": "value"}
            )

        assert job.job_id == "job_123"
        assert job.name == "test_job"
        assert job.script == "train.py"
        assert job.status == JobStatus.PENDING
        assert job.script_args == ["--epochs", "10"]

    @patch('scheduler.api.client.load_config')
    def test_submit_job_connection_error(self, mock_load_config):
        """Test submit_job raises ConnectionException on network error"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'post', side_effect=requests.exceptions.ConnectionError("Connection failed")):
            with pytest.raises(ConnectionException) as exc_info:
                client.submit_job("train.py", "2")

            assert "Failed to connect to head node" in str(exc_info.value)

    @patch('scheduler.api.client.load_config')
    def test_submit_job_invalid_response(self, mock_load_config):
        """Test submit_job raises ValidationException on invalid response"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Missing required fields

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(ValidationException) as exc_info:
                client.submit_job("train.py", "2")

            assert "Invalid response from server" in str(exc_info.value)

    @patch('scheduler.api.client.load_config')
    def test_submit_job_all_parameters(self, mock_load_config):
        """Test submit_job with all optional parameters"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_456",
            "name": "complex_job",
            "script": "train.py",
            "requirements": "4",
            "status": "pending",
            "submitted_at": "2025-01-01T00:00:00",
            "started_at": None,
            "completed_at": None,
            "assigned_node": None,
            "assigned_gpus": None,
            "exit_code": None,
            "error_message": None,
            "script_args": ["--arg1", "val1"],
            "working_dir": "/work",
            "env_vars": {"ENV": "prod"},
            "dependencies": ["job_123"],
            "priority": 10,
            "timeout": 3600
        }

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            job = client.submit_job(
                script="train.py",
                requirements="4",
                name="complex_job",
                script_args=["--arg1", "val1"],
                working_dir="/work",
                env_vars={"ENV": "prod"},
                dependencies=["job_123"],
                priority=10,
                timeout=3600
            )

        # Verify the payload sent
        call_kwargs = mock_post.call_args
        payload = call_kwargs[1]['json']
        assert payload["script"] == "train.py"
        assert payload["requirements"] == "4"
        assert payload["priority"] == 10
        assert payload["timeout"] == 3600


class TestGetJob:
    """Tests for get_job method"""

    @patch('scheduler.api.client.load_config')
    def test_get_job_success(self, mock_load_config):
        """Test successfully getting a job"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_123",
            "name": "test_job",
            "script": "train.py",
            "requirements": "2",
            "status": "running",
            "submitted_at": "2025-01-01T00:00:00",
            "started_at": "2025-01-01T00:01:00",
            "completed_at": None,
            "assigned_node": "worker-1",
            "assigned_gpus": [0, 1],
            "exit_code": None,
            "error_message": None,
            "script_args": None,
            "working_dir": None,
            "env_vars": None,
            "dependencies": None,
            "priority": 0,
            "timeout": None
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            job = client.get_job("job_123")

        assert job.job_id == "job_123"
        assert job.status == JobStatus.RUNNING
        assert job.assigned_node == "worker-1"
        assert job.assigned_gpus == [0, 1]

    @patch('scheduler.api.client.load_config')
    def test_get_job_not_found(self, mock_load_config):
        """Test get_job raises JobNotFoundException when job doesn't exist"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(JobNotFoundException) as exc_info:
                client.get_job("nonexistent")

            assert "Job nonexistent not found" in str(exc_info.value)

    @patch('scheduler.api.client.load_config')
    def test_get_job_connection_error(self, mock_load_config):
        """Test get_job raises ConnectionException on network error"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'get', side_effect=requests.exceptions.Timeout()):
            with pytest.raises(ConnectionException):
                client.get_job("job_123")


class TestListJobs:
    """Tests for list_jobs method"""

    @patch('scheduler.api.client.load_config')
    def test_list_jobs_success(self, mock_load_config):
        """Test successfully listing jobs"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "jobs": [
                {
                    "job_id": "job_1",
                    "name": "job1",
                    "script": "train1.py",
                    "requirements": "2",
                    "status": "running",
                    "submitted_at": "2025-01-01T00:00:00",
                    "started_at": None,
                    "completed_at": None,
                    "assigned_node": None,
                    "assigned_gpus": None,
                    "exit_code": None,
                    "error_message": None,
                    "priority": 0
                },
                {
                    "job_id": "job_2",
                    "name": "job2",
                    "script": "train2.py",
                    "requirements": "1",
                    "status": "pending",
                    "submitted_at": "2025-01-01T00:00:00",
                    "started_at": None,
                    "completed_at": None,
                    "assigned_node": None,
                    "assigned_gpus": None,
                    "exit_code": None,
                    "error_message": None,
                    "priority": 0
                }
            ]
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            jobs = client.list_jobs()

        assert len(jobs) == 2
        assert jobs[0].job_id == "job_1"
        assert jobs[1].job_id == "job_2"

    @patch('scheduler.api.client.load_config')
    def test_list_jobs_with_filter(self, mock_load_config):
        """Test listing jobs with status filter"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": []}

        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            client.list_jobs(status_filter="RUNNING", limit=10)

            # Verify params were passed
            call_kwargs = mock_get.call_args
            params = call_kwargs[1]['params']
            assert params["status"] == "RUNNING"
            assert params["limit"] == 10

    @patch('scheduler.api.client.load_config')
    def test_list_jobs_empty(self, mock_load_config):
        """Test listing jobs returns empty list when no jobs"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"jobs": []}

        with patch.object(client.session, 'get', return_value=mock_response):
            jobs = client.list_jobs()

        assert jobs == []


class TestCancelJob:
    """Tests for cancel_job method"""

    @patch('scheduler.api.client.load_config')
    def test_cancel_job_success(self, mock_load_config):
        """Test successfully canceling a job"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'delete', return_value=mock_response) as mock_delete:
            client.cancel_job("job_123")

            # Verify DELETE was called with correct endpoint
            mock_delete.assert_called_once()
            assert "/jobs/job_123" in mock_delete.call_args[0][0]

    @patch('scheduler.api.client.load_config')
    def test_cancel_job_not_found(self, mock_load_config):
        """Test cancel_job raises JobNotFoundException when job doesn't exist"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'delete', return_value=mock_response):
            with pytest.raises(JobNotFoundException):
                client.cancel_job("nonexistent")


class TestJobLogs:
    """Tests for log retrieval methods"""

    @patch('scheduler.api.client.load_config')
    def test_get_job_logs_success(self, mock_load_config):
        """Test successfully getting job logs"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Log line 1\nLog line 2\nLog line 3"

        with patch.object(client.session, 'get', return_value=mock_response):
            logs = client.get_job_logs("job_123")

        assert "Log line 1" in logs
        assert "Log line 3" in logs

    @patch('scheduler.api.client.load_config')
    def test_get_job_logs_with_parameters(self, mock_load_config):
        """Test getting job logs with lines limit and stderr"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "Error log"

        with patch.object(client.session, 'get', return_value=mock_response) as mock_get:
            client.get_job_logs("job_123", lines=50, stderr=True)

            # Verify params
            call_kwargs = mock_get.call_args
            params = call_kwargs[1]['params']
            assert params["lines"] == 50
            assert params["stderr"] == "true"

    @patch('scheduler.api.client.load_config')
    def test_get_job_logs_not_found(self, mock_load_config):
        """Test get_job_logs raises JobNotFoundException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(JobNotFoundException):
                client.get_job_logs("nonexistent")

    @patch('scheduler.api.client.load_config')
    def test_stream_job_logs_success(self, mock_load_config):
        """Test successfully streaming job logs"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = iter([
            "Line 1",
            "Line 2",
            "",  # Empty line should be filtered
            "Line 3"
        ])

        with patch.object(client.session, 'get', return_value=mock_response):
            lines = list(client.stream_job_logs("job_123"))

        assert len(lines) == 3
        assert lines[0] == "Line 1"
        assert lines[2] == "Line 3"

    @patch('scheduler.api.client.load_config')
    def test_stream_job_logs_not_found(self, mock_load_config):
        """Test stream_job_logs raises JobNotFoundException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(JobNotFoundException):
                list(client.stream_job_logs("nonexistent"))


class TestNodeMethods:
    """Tests for node-related methods"""

    @patch('scheduler.api.client.load_config')
    def test_list_nodes_success(self, mock_load_config):
        """Test successfully listing nodes"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        # API returns a list directly, not a dict with "nodes" key
        mock_response.json.return_value = [
            {
                "node_name": "worker-1",
                "address": "192.168.1.1:8265",
                "num_gpus": 4,
                "registered_at": "2025-01-01T00:00:00",
                "last_heartbeat": "2025-01-01T01:00:00",
                "gpus": [
                    {
                        "gpu_id": 0,
                        "utilization": 50,
                        "memory_used": 8000,
                        "memory_total": 16000,
                        "temperature": 65,
                        "power_draw": 150,
                        "power_limit": 250,
                        "assigned_job_id": None,
                        "stable_since": "2025-01-01T00:00:00"
                    }
                ]
            }
        ]

        with patch.object(client.session, 'get', return_value=mock_response):
            nodes = client.list_nodes()

        assert len(nodes) == 1
        assert nodes[0].node_name == "worker-1"
        assert nodes[0].num_gpus == 4
        assert len(nodes[0].gpus) == 1

    @patch('scheduler.api.client.load_config')
    def test_get_node_success(self, mock_load_config):
        """Test successfully getting a node"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "node_name": "worker-1",
            "address": "192.168.1.1:8265",
            "num_gpus": 2,
            "registered_at": "2025-01-01T00:00:00",
            "last_heartbeat": "2025-01-01T01:00:00",
            "gpus": []
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            node = client.get_node("worker-1")

        assert node.node_name == "worker-1"
        assert node.num_gpus == 2

    @patch('scheduler.api.client.load_config')
    def test_get_node_not_found(self, mock_load_config):
        """Test get_node raises NodeNotFoundException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 404

        with patch.object(client.session, 'get', return_value=mock_response):
            with pytest.raises(NodeNotFoundException):
                client.get_node("nonexistent")


class TestWorkerMethods:
    """Tests for worker-specific methods"""

    @patch('scheduler.api.client.load_config')
    def test_register_node_success(self, mock_load_config):
        """Test successfully registering a node"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "registered"}

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            result = client.register_node("worker-1", "192.168.1.1:8265", 4)

            assert result["status"] == "registered"
            # Verify payload
            call_kwargs = mock_post.call_args
            payload = call_kwargs[1]['json']
            assert payload["node_name"] == "worker-1"
            assert payload["num_gpus"] == 4

    @patch('scheduler.api.client.load_config')
    def test_send_heartbeat_success(self, mock_load_config):
        """Test successfully sending heartbeat"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200

        gpu_stats = [
            GPUStats(gpu_id=0, utilization=50, memory_used=8000,
                    memory_total=16000, temperature=65, power_draw=150, power_limit=250)
        ]

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client.send_heartbeat("worker-1", gpu_stats)

            # Verify payload contains serialized stats
            call_kwargs = mock_post.call_args
            payload = call_kwargs[1]['json']
            assert "gpu_stats" in payload
            assert len(payload["gpu_stats"]) == 1

    @patch('scheduler.api.client.load_config')
    def test_poll_for_job_with_job(self, mock_load_config):
        """Test polling for job when job is available"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "job_id": "job_123",
            "name": "polled_job",
            "script": "train.py",
            "requirements": "2",
            "status": "pending",
            "submitted_at": "2025-01-01T00:00:00",
            "started_at": None,
            "completed_at": None,
            "assigned_node": None,
            "assigned_gpus": None,
            "exit_code": None,
            "error_message": None,
            "priority": 0
        }

        with patch.object(client.session, 'get', return_value=mock_response):
            job = client.poll_for_job("worker-1", timeout=30)

        assert job is not None
        assert job.job_id == "job_123"

    @patch('scheduler.api.client.load_config')
    def test_poll_for_job_no_job(self, mock_load_config):
        """Test polling for job when no job is available"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 204  # No content

        with patch.object(client.session, 'get', return_value=mock_response):
            job = client.poll_for_job("worker-1", timeout=30)

        assert job is None

    @patch('scheduler.api.client.load_config')
    def test_poll_for_job_timeout(self, mock_load_config):
        """Test polling for job returns None on timeout"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'get', side_effect=requests.exceptions.Timeout()):
            job = client.poll_for_job("worker-1", timeout=30)

        assert job is None

    @patch('scheduler.api.client.load_config')
    def test_report_job_complete_success(self, mock_load_config):
        """Test successfully reporting job completion"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client.report_job_complete("job_123", exit_code=0)

            # Verify exit_code sent as param
            call_kwargs = mock_post.call_args
            params = call_kwargs[1]['params']
            assert params["exit_code"] == 0

    @patch('scheduler.api.client.load_config')
    def test_report_job_failed_success(self, mock_load_config):
        """Test successfully reporting job failure"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'post', return_value=mock_response) as mock_post:
            client.report_job_failed("job_123", "Out of memory")

            # Verify error_message sent as param
            call_kwargs = mock_post.call_args
            params = call_kwargs[1]['params']
            assert params["error_message"] == "Out of memory"


class TestHealthCheck:
    """Tests for health_check method"""

    @patch('scheduler.api.client.load_config')
    def test_health_check_healthy(self, mock_load_config):
        """Test health check returns True when server is healthy"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 200

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.health_check()

        assert result is True

    @patch('scheduler.api.client.load_config')
    def test_health_check_unhealthy(self, mock_load_config):
        """Test health check returns False when server is unhealthy"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 500

        with patch.object(client.session, 'get', return_value=mock_response):
            result = client.health_check()

        assert result is False

    @patch('scheduler.api.client.load_config')
    def test_health_check_connection_error(self, mock_load_config):
        """Test health check returns False on connection error"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'get', side_effect=requests.exceptions.ConnectionError()):
            result = client.health_check()

        assert result is False


class TestResponseParsing:
    """Tests for internal response parsing methods"""

    @patch('scheduler.api.client.load_config')
    def test_job_from_response_complete_job(self, mock_load_config):
        """Test parsing a completed job from response"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        data = {
            "job_id": "job_123",
            "name": "completed_job",
            "script": "train.py",
            "requirements": "2",
            "status": "completed",
            "submitted_at": "2025-01-01T00:00:00",
            "started_at": "2025-01-01T00:01:00",
            "completed_at": "2025-01-01T01:00:00",
            "assigned_node": "worker-1",
            "assigned_gpus": [0, 1],
            "exit_code": 0,
            "error_message": None,
            "script_args": ["--epochs", "100"],
            "working_dir": "/workspace",
            "env_vars": {"CUDA_VISIBLE_DEVICES": "0,1"},
            "dependencies": ["job_100"],
            "priority": 5,
            "timeout": 7200
        }

        job = client._job_from_response(data)

        assert job.job_id == "job_123"
        assert job.status == JobStatus.COMPLETED
        assert job.exit_code == 0
        assert job.assigned_gpus == [0, 1]
        assert job.priority == 5
        assert job.timeout == 7200
        assert isinstance(job.submitted_at, datetime)
        assert isinstance(job.completed_at, datetime)

    @patch('scheduler.api.client.load_config')
    def test_node_from_response_with_gpus(self, mock_load_config):
        """Test parsing a node with GPUs from response"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        data = {
            "node_name": "worker-1",
            "address": "192.168.1.1:8265",
            "num_gpus": 2,
            "registered_at": "2025-01-01T00:00:00",
            "last_heartbeat": "2025-01-01T01:00:00",
            "gpus": [
                {
                    "gpu_id": 0,
                    "utilization": 75,
                    "memory_used": 12000,
                    "memory_total": 16000,
                    "temperature": 70,
                    "power_draw": 200,
                    "power_limit": 250,
                    "assigned_job_id": "job_123",
                    "stable_since": "2025-01-01T00:30:00"
                },
                {
                    "gpu_id": 1,
                    "utilization": 10,
                    "memory_used": 1000,
                    "memory_total": 16000,
                    "temperature": 45,
                    "power_draw": 50,
                    "power_limit": 250,
                    "assigned_job_id": None,
                    "stable_since": "2025-01-01T00:00:00"
                }
            ]
        }

        node = client._node_from_response(data)

        assert node.node_name == "worker-1"
        assert node.num_gpus == 2
        assert len(node.gpus) == 2
        assert node.gpus[0].assigned_job_id == "job_123"
        assert node.gpus[1].assigned_job_id is None
        assert isinstance(node.gpus[0].stable_since, datetime)


class TestExceptionHandling:
    """Tests for exception handling across methods"""

    @patch('scheduler.api.client.load_config')
    def test_http_500_raises_connection_exception(self, mock_load_config):
        """Test HTTP 500 errors raise ConnectionException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()

        with patch.object(client.session, 'post', return_value=mock_response):
            with pytest.raises(ConnectionException):
                client.submit_job("train.py", "2")

    @patch('scheduler.api.client.load_config')
    def test_timeout_raises_connection_exception(self, mock_load_config):
        """Test timeout errors raise ConnectionException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'get', side_effect=requests.exceptions.Timeout()):
            with pytest.raises(ConnectionException):
                client.list_jobs()

    @patch('scheduler.api.client.load_config')
    def test_network_error_raises_connection_exception(self, mock_load_config):
        """Test network errors raise ConnectionException"""
        mock_load_config.return_value = Mock()
        client = SchedulerClient(address="test:9000")

        with patch.object(client.session, 'delete', side_effect=requests.exceptions.RequestException()):
            with pytest.raises(ConnectionException):
                client.cancel_job("job_123")
