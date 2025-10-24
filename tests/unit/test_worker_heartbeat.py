"""Tests for heartbeat sender functionality"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock

from scheduler.worker.heartbeat import HeartbeatSender
from scheduler.core.models import GPUStats, Job, JobRequirement, JobStatus


class TestHeartbeatSender:
    """Tests for HeartbeatSender class"""

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_init(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat sender initialization"""
        mock_gpu_monitor_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_send_heartbeat_success(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test successful heartbeat sending"""
        mock_gpu_monitor_instance = Mock()
        mock_stats = [
            GPUStats(gpu_id=0, utilization=50.0, memory_used=1024, memory_total=2048, temperature=60, power_draw=100, power_limit=250),
            GPUStats(gpu_id=1, utilization=75.0, memory_used=1536, memory_total=2048, temperature=65, power_draw=150, power_limit=250)
        ]
        mock_gpu_monitor_instance.get_latest_stats.return_value = mock_stats

        mock_client_instance = Mock()
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
        mock_client_instance.send_heartbeat.assert_called_once_with("test-node", mock_stats)

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_send_heartbeat_failure(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test heartbeat sending failure"""
        mock_gpu_monitor_instance = Mock()
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_poll_for_job_with_job(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job when job is available"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()

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
        mock_client_instance.poll_for_job.assert_called_once_with("test-node", timeout=30)

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_poll_for_job_no_job(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job when no job available"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_poll_for_job_error(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test polling for job with error"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_start_heartbeat(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test starting heartbeat thread"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_stop_heartbeat(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test stopping heartbeat thread"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_start_already_running(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test starting heartbeat when already running"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_stop_not_running(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test stopping heartbeat when not running"""
        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    @patch('time.sleep')
    def test_heartbeat_loop_sends_periodically(self, mock_sleep, mock_gpu_monitor, mock_client_class, test_config):
        """Test that heartbeat loop sends heartbeats periodically"""
        mock_gpu_monitor_instance = Mock()
        mock_gpu_monitor_instance.get_latest_stats.return_value = []

        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_heartbeat_loop_error_handling(self, mock_gpu_monitor, mock_client_class, test_config):
        """Test that heartbeat loop handles errors gracefully"""
        mock_gpu_monitor_instance = Mock()
        mock_gpu_monitor_instance.get_latest_stats.side_effect = Exception("GPU error")

        mock_client_instance = Mock()
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

    @patch('scheduler.worker.heartbeat.SchedulerClient')
    @patch('scheduler.worker.heartbeat.GPUMonitor')
    def test_heartbeat_interval_configuration(self, mock_gpu_monitor, mock_client_class):
        """Test that heartbeat interval is read from configuration"""
        from scheduler.core.config import Config, WorkerConfig

        mock_gpu_monitor_instance = Mock()
        mock_client_instance = Mock()
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
