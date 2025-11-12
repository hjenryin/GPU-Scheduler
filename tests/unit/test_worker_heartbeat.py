"""Tests for heartbeat sender functionality"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock, create_autospec

from scheduler.worker.heartbeat import HeartbeatSender
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.core.models import GPUStats, Job, JobRequirement, JobStatus
from scheduler.api.client import SchedulerClient
from scheduler.api.schemas import HeartbeatResponse


class TestHeartbeatSender:
    """Tests for HeartbeatSender class"""

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_init(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat sender initialization"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        node_name = "test-node"
        head_address = "localhost:8265"

        sender = HeartbeatSender(
            node_name=node_name,
            head_address=head_address,
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        assert sender.node_name == node_name
        assert sender.head_address == head_address
        assert sender.gpu_monitor == mock_gpu_monitor_instance
        assert sender.config == test_config
        assert sender.running is False
        assert sender.heartbeat_thread is None

        # Check client was created
        mock_client_class.assert_called_once_with(address=head_address, config=test_config)

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_success(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test successful heartbeat sending"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_stats = [
            GPUStats(gpu_id=0, utilization=50.0, memory_used=1024, memory_total=2048, temperature=60, power_draw=100, power_limit=250),
            GPUStats(gpu_id=1, utilization=75.0, memory_used=1536, memory_total=2048, temperature=65, power_draw=150, power_limit=250)
        ]
        mock_gpu_monitor_instance.get_latest_stats.return_value = mock_stats

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=True, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        result = sender.send_heartbeat()

        assert result is True
        mock_gpu_monitor_instance.get_latest_stats.assert_called_once()
        # When shutdown_requested=True, send_heartbeat is called twice (confirmation)
        assert mock_client_instance.send_heartbeat.call_count == 2

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_failure(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat sending failure"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_instance.send_heartbeat.side_effect = Exception("Connection error")
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        result = sender.send_heartbeat()

        assert result is False

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_poll_for_job_with_job(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job when job is available"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)

        mock_job = Job(
            job_id="job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1"),
            status=JobStatus.PENDING
        )
        mock_client_instance.poll_for_job.return_value = mock_job
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        job = sender.poll_for_job()

        assert job == mock_job
        # Should use the config value (test_config has job_poll_timeout from conftest)
        mock_client_instance.poll_for_job.assert_called_once_with(
            "test-node",
            timeout=test_config.worker.job_poll_timeout
        )

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_poll_for_job_no_job(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job when no job available"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_instance.poll_for_job.return_value = None
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        job = sender.poll_for_job()

        assert job is None

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_poll_for_job_error(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job with error"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_instance.poll_for_job.side_effect = Exception("Network error")
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        job = sender.poll_for_job()

        assert job is None

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_start_heartbeat(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test starting heartbeat thread"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=False, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        sender.start()

        assert sender.running is True
        assert sender.heartbeat_thread is not None
        assert sender.heartbeat_thread.is_alive()

        # Clean up
        sender.stop()

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_stop_heartbeat(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test stopping heartbeat thread"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []
        
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=False, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        sender.start()
        assert sender.running is True

        sender.stop()
        assert sender.running is False

        # Give thread time to finish
        if sender.heartbeat_thread:
            sender.heartbeat_thread.join(timeout=1)

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_start_already_running(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test starting heartbeat when already running"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=False, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        sender.start()
        # Try to start again
        sender.start()  # Should just log warning

        assert sender.running is True

        sender.stop()

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_stop_not_running(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test stopping heartbeat when not running"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Stop without starting (should just log warning)
        sender.stop()

        assert sender.running is False

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    @patch('time.sleep', autospec=True)
    def test_heartbeat_loop_sends_periodically(self, mock_sleep, mock_gpu_monitor, mock_client_class, test_config):
        """Test that heartbeat loop sends heartbeats periodically"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=False, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        # Mock sleep to control loop iterations
        call_count = [0]

        def sleep_side_effect(duration):
            call_count[0] += 1
            if call_count[0] >= 3:
                # Stop after 3 iterations
                sender.running = False

        mock_sleep.side_effect = sleep_side_effect

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        sender.start()

        # Wait for thread to complete
        time.sleep(0.1)
        sender.heartbeat_thread.join(timeout=1)

        # Should have sent multiple heartbeats
        assert mock_client_instance.send_heartbeat.call_count >= 3

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_heartbeat_loop_error_handling(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test that heartbeat loop handles errors gracefully"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.side_effect = Exception("GPU error")

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        sender.start()

        # Wait briefly for thread to process errors
        time.sleep(0.2)

        # Thread should still be alive despite errors
        assert sender.running is True

        sender.stop()
        
        # Give thread time to finish
        if sender.heartbeat_thread:
            sender.heartbeat_thread.join(timeout=1)

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_heartbeat_interval_configuration(self, mock_gpu_monitor, mock_client_class):
        """Test that heartbeat interval is read from configuration"""
        from scheduler.core.config import Config, WorkerConfig

        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_class.return_value = mock_client_instance

        # Create config with specific interval
        worker_config = WorkerConfig(heartbeat_interval=15)
        config = Config(worker=worker_config)

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=config
        )

        assert sender.heartbeat_interval == 15

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_with_shutdown_requested(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat detects shutdown request from head node"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_stats = [
            GPUStats(gpu_id=0, utilization=50.0, memory_used=1024, memory_total=2048, temperature=60, power_draw=100, power_limit=250)
        ]
        mock_gpu_monitor_instance.get_latest_stats.return_value = mock_stats

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=True, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        result = sender.send_heartbeat()

        assert result is True
        # When shutdown_requested=True, send_heartbeat is called twice (initial + confirmation)
        assert mock_client_instance.send_heartbeat.call_count == 2

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_without_shutdown_requested(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat when no shutdown is requested"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_stats = [
            GPUStats(gpu_id=0, utilization=50.0, memory_used=1024, memory_total=2048, temperature=60, power_draw=100, power_limit=250)
        ]
        mock_gpu_monitor_instance.get_latest_stats.return_value = mock_stats

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_response = HeartbeatResponse(status="ok", shutdown_requested=False, log_requests=[])
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        result = sender.send_heartbeat()

        assert result is False
        assert mock_client_instance.send_heartbeat.call_count == 1

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_is_shutdown_requested(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test is_shutdown_requested method"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Initially running should be False, so shutdown is requested (not running)
        assert sender.is_shutdown_requested() is True
        
        # Start the sender
        sender.running = True
        assert sender.is_shutdown_requested() is False
        
        # Stop it
        sender.running = False
        assert sender.is_shutdown_requested() is True

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_with_cleanup_callback(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test send_heartbeat calls cleanup callback with job IDs"""
        from scheduler.api.schemas import HeartbeatResponse
        
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []
        mock_gpu_monitor.return_value = mock_gpu_monitor_instance

        # Create mock response with recorded and running job IDs
        mock_response = create_autospec(HeartbeatResponse, instance=True, spec_set=True)
        mock_response.shutdown_requested = False
        mock_response.recorded_job_ids = ["job-1", "job-2", "job-3"]
        mock_response.running_job_ids = ["job-1"]
        
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Set cleanup callback
        cleanup_called = []
        def cleanup_callback(recorded, running):
            cleanup_called.append((recorded, running))
        
        sender.set_cleanup_callback(cleanup_callback)

        # Send heartbeat
        result = sender.send_heartbeat()

        # Verify callback was called with correct arguments
        assert len(cleanup_called) == 1
        assert cleanup_called[0] == (["job-1", "job-2", "job-3"], ["job-1"])
        assert result is False

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_backward_compatibility_active_job_ids(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test send_heartbeat uses active_job_ids for backward compatibility"""
        from scheduler.api.schemas import HeartbeatResponse
        
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []
        mock_gpu_monitor.return_value = mock_gpu_monitor_instance

        # Create mock response with old active_job_ids field (no recorded_job_ids)
        mock_response = create_autospec(HeartbeatResponse, instance=True, spec_set=True)
        mock_response.shutdown_requested = False
        mock_response.recorded_job_ids = []  # Empty
        mock_response.running_job_ids = []
        mock_response.active_job_ids = ["job-old-1", "job-old-2"]  # Old field
        
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_instance.send_heartbeat.return_value = mock_response
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Set cleanup callback
        cleanup_called = []
        def cleanup_callback(recorded, running):
            cleanup_called.append((recorded, running))
        
        sender.set_cleanup_callback(cleanup_callback)

        # Send heartbeat
        sender.send_heartbeat()

        # Verify callback was called with active_job_ids (backward compatibility)
        assert len(cleanup_called) == 1
        assert cleanup_called[0] == (["job-old-1", "job-old-2"], [])

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_send_heartbeat_confirmation_failure(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test send_heartbeat handles failure in shutdown confirmation gracefully"""
        from scheduler.api.schemas import HeartbeatResponse
        
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor_instance.get_latest_stats.return_value = []
        mock_gpu_monitor.return_value = mock_gpu_monitor_instance

        mock_response = create_autospec(HeartbeatResponse, instance=True, spec_set=True)
        mock_response.shutdown_requested = True
        
        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        # First call returns shutdown request, second call (confirmation) fails
        mock_client_instance.send_heartbeat.side_effect = [
            mock_response,  # Initial heartbeat
            Exception("Network error")  # Confirmation fails
        ]
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Send heartbeat - should still return True despite confirmation failure
        result = sender.send_heartbeat()
        assert result is True
        # Should have attempted to send confirmation (2 calls total)
        assert mock_client_instance.send_heartbeat.call_count == 2

    @patch('scheduler.worker.heartbeat.SchedulerClient', autospec=True)
    @patch('scheduler.worker.heartbeat.GPUMonitor', autospec=True)
    def test_set_purge_callback_backward_compatibility(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test set_purge_callback calls set_cleanup_callback for backward compatibility"""
        mock_gpu_monitor_instance = create_autospec(GPUMonitor, instance=True, spec_set=True)
        mock_gpu_monitor.return_value = mock_gpu_monitor_instance

        mock_client_instance = create_autospec(SchedulerClient, instance=True, spec_set=True)
        mock_client_class.return_value = mock_client_instance

        sender = HeartbeatSender(
            node_name="test-node",
            head_address="localhost:8265",
            gpu_monitor=mock_gpu_monitor_instance,
            config=test_config
        )

        # Use deprecated set_purge_callback
        test_callback = lambda x, y: None
        sender.set_purge_callback(test_callback)

        # Verify it set the cleanup callback
        assert sender.cleanup_callback == test_callback
