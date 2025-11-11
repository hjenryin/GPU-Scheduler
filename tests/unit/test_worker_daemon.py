"""Tests for worker daemon functionality"""
import pytest
import signal
import time
from unittest.mock import Mock, patch, MagicMock, call, create_autospec

from scheduler.worker.daemon import WorkerDaemon
from scheduler.core.exceptions import ConnectionException
from scheduler.core.models import Job, JobRequirement, JobStatus
from scheduler.api.client import SchedulerClient


class TestWorkerDaemon:
    """Tests for WorkerDaemon class"""

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_init_with_auto_detect_gpus(self, mock_file_handler, mock_gpu_monitor,
                                       mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test daemon initialization with GPU auto-detection"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 4
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")

        assert daemon.node_name == "test-node"
        assert daemon.num_gpus == 4
        assert daemon.running is False
        assert daemon.active_jobs == {}

        # Verify GPU monitor was created
        mock_gpu_monitor.assert_called_once_with(test_config)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_init_with_specified_gpus(self, mock_file_handler, mock_gpu_monitor,
                                      mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test daemon initialization with specified GPU count"""
        mock_monitor_instance = Mock()
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        daemon = WorkerDaemon(test_config, node_name="test-node", num_gpus=2)

        assert daemon.num_gpus == 2
        # detect_gpus should not be called
        mock_monitor_instance.detect_gpus.assert_not_called()

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    @patch('scheduler.worker.daemon.get_local_ip', autospec=True)
    def test_init_address_configuration(self, mock_get_ip, mock_file_handler, mock_gpu_monitor,
                                       mock_job_executor, mock_heartbeat, mock_client):
        """Test address configuration"""
        from scheduler.core.config import Config, HeadConfig

        mock_get_ip.return_value = "192.168.1.100"
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        # Test with config.address set
        config1 = Config(address="head-node:8265")
        daemon = WorkerDaemon(config1, node_name="test-node")

        assert daemon.head_address == "head-node:8265"

        # Test without config.address (use head.port)
        head_config = HeadConfig(port=9999)
        config2 = Config(address=None, head=head_config)
        daemon2 = WorkerDaemon(config2, node_name="test-node2")

        assert daemon2.head_address == "localhost:9999"

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_start_success(self, mock_file_handler, mock_gpu_monitor,
                          mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test successful daemon start"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.stop_monitoring = Mock()
        mock_monitor_instance.start_monitoring = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat_instance.stop = Mock()
        mock_heartbeat_instance.start = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {"status": "ok"}
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.start()

        assert daemon.running is True

        # Verify registration was called
        mock_client_instance.register_node.assert_called_once()

        # Verify components were started
        mock_monitor_instance.start_monitoring.assert_called_once()
        mock_heartbeat_instance.start.assert_called_once()
        
        # Clean up
        daemon.stop(graceful=False)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_start_registration_failure(self, mock_file_handler, mock_gpu_monitor,
                                       mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test daemon start with registration failure"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.side_effect = Exception("Connection refused")
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")

        with pytest.raises(ConnectionException):
            daemon.start()

        # Daemon should not be running
        assert daemon.running is False

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_start_already_running(self, mock_file_handler, mock_gpu_monitor,
                                   mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test starting daemon when already running"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.stop_monitoring = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance
        
        mock_heartbeat_instance = Mock()
        mock_heartbeat_instance.stop = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.start()

        # Try to start again
        daemon.start()  # Should just log warning

        assert daemon.running is True
        
        # Clean up
        daemon.stop(graceful=False)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_stop_graceful_no_job(self, mock_file_handler, mock_gpu_monitor,
                                  mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test graceful daemon stop with no running job"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.start()

        daemon.stop(graceful=True)

        assert daemon.running is False
        mock_heartbeat_instance.stop.assert_called_once()
        mock_monitor_instance.stop_monitoring.assert_called_once()

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    @patch('time.sleep', autospec=True)
    def test_stop_graceful_with_completing_job(self, mock_sleep, mock_file_handler, mock_gpu_monitor,
                                               mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test graceful stop waits for job to complete"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        # First call: still running, second call: completed
        mock_executor_instance.get_job_status.side_effect = [
            (True, None),
            (False, 0)
        ]
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.start()

        # Set a current job
        daemon.current_job = Mock(job_id="job-001")
        daemon.current_job_pid = 12345

        daemon.stop(graceful=True)

        # Should have waited for job
        assert mock_executor_instance.get_job_status.call_count == 2

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    @patch('time.sleep', autospec=True)
    @patch('time.time', autospec=True)
    def test_stop_graceful_timeout_terminates_job(self, mock_time, mock_sleep, mock_file_handler,
                                                  mock_gpu_monitor, mock_job_executor,
                                                  mock_heartbeat, mock_client, test_config):
        """Test graceful stop terminates job after timeout"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.stop_monitoring = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        # Job never completes
        mock_executor_instance.get_job_status.return_value = (True, None)
        mock_job_executor.return_value = mock_executor_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat_instance.stop = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        # Mock time to simulate timeout: start_time=0, then after timeout it becomes 61
        call_count = [0]
        def time_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return 0  # start_time
            else:
                return 61  # After timeout
        
        mock_time.side_effect = time_side_effect

        daemon = WorkerDaemon(test_config, node_name="test-node")
        # Don't actually start (to avoid thread issues)
        daemon.running = True
        daemon.current_job = Mock(job_id="job-001")
        daemon.current_job_pid = 12345

        daemon.stop(graceful=True)

        # Should have terminated the job
        mock_executor_instance.terminate_job.assert_called_once_with(12345)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_stop_not_running(self, mock_file_handler, mock_gpu_monitor,
                              mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test stopping daemon when not running"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")

        # Stop without starting
        daemon.stop()

        assert daemon.running is False

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_execute_job_success(self, mock_file_handler, mock_gpu_monitor,
                                 mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test successful job execution"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.return_value = 12345
        # Job completes successfully
        mock_executor_instance.get_job_status.return_value = (False, 0)
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True

        job = Job(
            job_id="job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("2"),
            status=JobStatus.PENDING,
            assigned_gpus=[0, 1]
        )

        daemon._execute_job(job)

        # Verify job was executed
        mock_executor_instance.execute_job.assert_called_once_with(job, [0, 1])

        # Verify completion was reported
        mock_client_instance.report_job_complete.assert_called_once_with("job-001", 0)

        # Job should be cleared
        assert daemon.current_job is None
        assert daemon.current_job_pid is None

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_execute_job_failure(self, mock_file_handler, mock_gpu_monitor,
                                 mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test job execution failure"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.return_value = 12345
        # Job fails
        mock_executor_instance.get_job_status.return_value = (False, 1)
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True

        job = Job(
            job_id="job-002",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )

        daemon._execute_job(job)

        # Verify failure was reported
        mock_client_instance.report_job_failed.assert_called_once()
        call_args = mock_client_instance.report_job_failed.call_args
        assert call_args[0][0] == "job-002"
        assert "Exit code: 1" in call_args[0][1]

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_execute_job_no_assigned_gpus(self, mock_file_handler, mock_gpu_monitor,
                                          mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test job execution when no GPUs are assigned (use all)"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 4
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.return_value = 12345
        mock_executor_instance.get_job_status.return_value = (False, 0)
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node", num_gpus=4)
        daemon.running = True

        job = Job(
            job_id="job-003",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("4"),
            status=JobStatus.PENDING
            # No assigned_gpus
        )

        daemon._execute_job(job)

        # Should use all GPUs
        call_args = mock_executor_instance.execute_job.call_args
        assert call_args[0][1] == [0, 1, 2, 3]

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_execute_job_exception_during_execution(self, mock_file_handler, mock_gpu_monitor,
                                                    mock_job_executor, mock_heartbeat,
                                                    mock_client, test_config):
        """Test handling of exception during job execution"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.side_effect = Exception("Execution failed")
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True

        job = Job(
            job_id="job-004",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )

        daemon._execute_job(job)

        # Verify failure was reported
        mock_client_instance.report_job_failed.assert_called_once_with("job-004", "Execution failed")

        # Job should not be added to active_jobs since execution failed
        assert job.job_id not in daemon.active_jobs

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_register_with_head(self, mock_file_handler, mock_gpu_monitor,
                                mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test worker registration with head node"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {"status": "registered"}
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node", num_gpus=2)

        daemon.register_with_head()

        # Verify registration was called correctly
        mock_client_instance.register_node.assert_called_once()
        call_args = mock_client_instance.register_node.call_args
        assert call_args[1]['node_name'] == "test-node"
        assert call_args[1]['num_gpus'] == 2

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_signal_handler(self, mock_file_handler, mock_gpu_monitor,
                           mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test signal handler for graceful shutdown"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.start()

        # Simulate signal
        daemon._signal_handler(signal.SIGTERM, None)

        # Daemon should be stopped
        assert daemon.running is False

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    @patch('scheduler.worker.daemon.time.sleep', autospec=True)
    def test_execute_job_calls_cleanup_on_completion(self, mock_sleep, mock_file_handler, 
                                                     mock_gpu_monitor, mock_job_executor,
                                                     mock_heartbeat, mock_client, test_config, sample_job):
        """Test that cleanup_job is called when job completes successfully"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.return_value = 12345
        # Job completes immediately
        mock_executor_instance.get_job_status.return_value = (False, 0)
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True
        
        # Execute job
        daemon._execute_job(sample_job)

        # Verify cleanup_job was called
        mock_executor_instance.cleanup_job.assert_called_once_with(sample_job)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    @patch('scheduler.worker.daemon.time.sleep', autospec=True)
    def test_execute_job_calls_cleanup_on_failure(self, mock_sleep, mock_file_handler,
                                                   mock_gpu_monitor, mock_job_executor,
                                                   mock_heartbeat, mock_client, test_config, sample_job):
        """Test that cleanup_job is called when job fails"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        mock_executor_instance.execute_job.return_value = 12345
        # Job fails with exit code 1
        mock_executor_instance.get_job_status.return_value = (False, 1)
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True
        
        # Execute job
        daemon._execute_job(sample_job)

        # Verify cleanup_job was called
        mock_executor_instance.cleanup_job.assert_called_once_with(sample_job)

    @patch('scheduler.worker.daemon.SchedulerClient', autospec=True)
    @patch('scheduler.worker.daemon.HeartbeatSender', autospec=True)
    @patch('scheduler.worker.daemon.JobExecutor', autospec=True)
    @patch('scheduler.worker.daemon.GPUMonitor', autospec=True)
    @patch('scheduler.worker.daemon.FileHandler', autospec=True)
    def test_execute_job_calls_cleanup_on_exception(self, mock_file_handler,
                                                    mock_gpu_monitor, mock_job_executor,
                                                    mock_heartbeat, mock_client, test_config, sample_job):
        """Test that cleanup_job is called when job execution raises exception"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_executor_instance = Mock()
        # Simulate exception during execution
        mock_executor_instance.execute_job.side_effect = RuntimeError("Test error")
        mock_job_executor.return_value = mock_executor_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.running = True
        
        # Execute job (should handle exception)
        daemon._execute_job(sample_job)

        # Verify cleanup_job was called
        mock_executor_instance.cleanup_job.assert_called_once_with(sample_job)

    @patch("scheduler.worker.daemon.SchedulerClient", autospec=True)
    @patch("scheduler.worker.daemon.HeartbeatSender", autospec=True)
    @patch("scheduler.worker.daemon.JobExecutor", autospec=True)
    @patch("scheduler.worker.daemon.GPUMonitor", autospec=True)
    @patch("scheduler.worker.daemon.FileHandler", autospec=True)
    def test_register_with_head_extracts_rsync_port(self, mock_file_handler, mock_gpu_monitor,
                                                      mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test that worker extracts rsync_port from registration response"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_file_handler_instance = Mock()
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {
            "status": "registered",
            "node_name": "test-node",
            "rsync_port": 8873
        }
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.register_with_head()

        assert daemon.rsync_port == 8873

    @patch("scheduler.worker.daemon.SchedulerClient", autospec=True)
    @patch("scheduler.worker.daemon.HeartbeatSender", autospec=True)
    @patch("scheduler.worker.daemon.JobExecutor", autospec=True)
    @patch("scheduler.worker.daemon.GPUMonitor", autospec=True)
    @patch("scheduler.worker.daemon.FileHandler", autospec=True)
    def test_register_with_head_handles_no_rsync_port(self, mock_file_handler, mock_gpu_monitor,
                                                        mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test that worker handles registration response without rsync_port"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_file_handler_instance = Mock()
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {
            "status": "registered",
            "node_name": "test-node"
        }
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")
        daemon.register_with_head()

        assert daemon.rsync_port is None

    @patch("scheduler.worker.daemon.SchedulerClient", autospec=True)
    @patch("scheduler.worker.daemon.HeartbeatSender", autospec=True)
    @patch("scheduler.worker.daemon.JobExecutor", autospec=True)
    @patch("scheduler.worker.daemon.GPUMonitor", autospec=True)
    @patch("scheduler.worker.daemon.FileHandler", autospec=True)
    def test_start_sets_running_before_starting_threads(self, mock_file_handler, mock_gpu_monitor,
                                                         mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test that daemon.running is set to True before starting threads (race condition fix)"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_monitor_instance.start_monitoring = Mock()
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_file_handler_instance = Mock()
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat_instance.start = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {
            "status": "registered",
            "node_name": "test-node",
            "rsync_port": 8873
        }
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")

        running_when_called = []

        def mock_start_log_sync(port):
            running_when_called.append(daemon.running)

        daemon._start_log_sync = mock_start_log_sync
        daemon.start()

        assert len(running_when_called) == 1
        assert running_when_called[0] is True

        daemon.stop(graceful=False)

    @patch("scheduler.worker.daemon.SchedulerClient", autospec=True)
    @patch("scheduler.worker.daemon.HeartbeatSender", autospec=True)
    @patch("scheduler.worker.daemon.JobExecutor", autospec=True)
    @patch("scheduler.worker.daemon.GPUMonitor", autospec=True)
    @patch("scheduler.worker.daemon.FileHandler", autospec=True)
    def test_start_log_sync_not_called_when_rsync_port_none(self, mock_file_handler, mock_gpu_monitor,
                                                              mock_job_executor, mock_heartbeat, mock_client, test_config):
        """Test that log sync is not started when rsync_port is None"""
        mock_monitor_instance = Mock()
        mock_monitor_instance.detect_gpus.return_value = 2
        mock_monitor_instance.start_monitoring = Mock()
        mock_gpu_monitor.return_value = mock_monitor_instance

        # Mock file handler with create_autospec
        from scheduler.worker.file_handler import FileHandler
        mock_file_handler_instance = create_autospec(FileHandler, instance=True, spec_set=True)
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_file_handler_instance = Mock()
        mock_file_handler_instance.cleanup_old_logs.return_value = 0
        mock_file_handler.return_value = mock_file_handler_instance

        mock_heartbeat_instance = Mock()
        mock_heartbeat_instance.start = Mock()
        mock_heartbeat.return_value = mock_heartbeat_instance

        mock_client_instance = Mock(spec_set=SchedulerClient)
        mock_client_instance.register_node.return_value = {
            "status": "registered",
            "node_name": "test-node",
            "rsync_port": None
        }
        mock_client.return_value = mock_client_instance

        daemon = WorkerDaemon(test_config, node_name="test-node")

        start_log_sync_called = []

        def mock_start_log_sync(port):
            start_log_sync_called.append(True)

        daemon._start_log_sync = mock_start_log_sync
        daemon.start()

        assert len(start_log_sync_called) == 0

        daemon.stop(graceful=False)

