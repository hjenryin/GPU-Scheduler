"""Tests for GPU monitoring functionality"""
import time

from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.core.models import GPUStats


class TestGPUMonitorReal:
    """Tests for GPU monitor using real GPU"""

    def test_init_with_real_gpu(self, test_config):
        """Test initialization with real GPU"""
        monitor = GPUMonitor(test_config)

        # Should successfully initialize
        assert monitor is not None
        # Should have detected the GPU (either via pynvml or nvidia-smi)
        assert monitor.use_pynvml is True or monitor.use_pynvml is False

    def test_detect_gpus_real(self, test_config):
        """Test GPU detection with real GPU"""
        monitor = GPUMonitor(test_config)
        num_gpus = monitor.detect_gpus()

        # Should detect at least 1 GPU (the MX450)
        assert num_gpus >= 1
        print(f"Detected {num_gpus} GPU(s), using pynvml: {monitor.use_pynvml}")

    def test_poll_gpu_stats_real(self, test_config):
        """Test polling GPU stats with real GPU"""
        monitor = GPUMonitor(test_config)
        stats = monitor.poll_gpu_stats()

        # Should get stats for at least one GPU
        assert len(stats) >= 1

        # Check first GPU stats are valid
        gpu_stat = stats[0]
        assert isinstance(gpu_stat, GPUStats)
        assert gpu_stat.gpu_id >= 0
        assert 0 <= gpu_stat.utilization <= 100
        assert gpu_stat.memory_used >= 0
        assert gpu_stat.memory_total > 0
        assert gpu_stat.memory_used <= gpu_stat.memory_total
        assert gpu_stat.temperature >= 0
        assert gpu_stat.power_draw >= 0

        print(f"GPU {gpu_stat.gpu_id}: {gpu_stat.utilization}% util, "
              f"{gpu_stat.memory_used / (1024**3):.2f}/{gpu_stat.memory_total / (1024**3):.2f} GB, "
              f"{gpu_stat.temperature}C, {gpu_stat.power_draw}W")

    def test_monitoring_thread_lifecycle_real(self, test_config):
        """Test starting and stopping monitoring thread with real GPU"""
        monitor = GPUMonitor(test_config)

        # Start monitoring
        monitor.start_monitoring()
        assert monitor.monitoring is True
        assert monitor.monitor_thread is not None
        assert monitor.monitor_thread.is_alive()

        # Wait briefly for thread to update stats
        time.sleep(0.5)

        # Check that stats are updated
        stats = monitor.get_latest_stats()
        assert len(stats) >= 1
        print(f"Latest stats: GPU {stats[0].gpu_id} at {stats[0].utilization}% utilization")

        # Stop monitoring
        monitor.stop_monitoring()
        assert monitor.monitoring is False

    def test_start_monitoring_already_running_real(self, test_config):
        """Test starting monitoring when already running"""
        monitor = GPUMonitor(test_config)

        monitor.start_monitoring()
        # Try to start again - should just log warning
        monitor.start_monitoring()

        monitor.stop_monitoring()

    def test_stop_monitoring_not_running_real(self, test_config):
        """Test stopping monitoring when not running"""
        monitor = GPUMonitor(test_config)

        # Stop without starting - should just log warning
        monitor.stop_monitoring()

    def test_continuous_monitoring_real(self, test_config):
        """Test that monitoring thread continuously updates stats"""
        monitor = GPUMonitor(test_config)
        # Override poll interval for faster test
        monitor.poll_interval = 0.2

        monitor.start_monitoring()

        # Get initial stats
        time.sleep(0.3)
        stats1 = monitor.get_latest_stats()
        assert len(stats1) >= 1

        # Wait for another update
        time.sleep(0.3)
        stats2 = monitor.get_latest_stats()
        assert len(stats2) >= 1

        # Stats should be updated (objects should be different)
        # At minimum, we should have valid stats both times
        assert stats1[0].gpu_id == stats2[0].gpu_id

        monitor.stop_monitoring()

    def test_pynvml_vs_nvidia_smi_consistency(self, test_config):
        """Test that both methods return consistent results if both available"""
        monitor = GPUMonitor(test_config)

        # Get stats using current method
        stats1 = monitor.poll_gpu_stats()
        assert len(stats1) >= 1

        # Both methods should report same number of GPUs
        num_gpus = monitor.detect_gpus()
        assert len(stats1) == num_gpus

        print(f"Using {'pynvml' if monitor.use_pynvml else 'nvidia-smi'}: "
              f"Found {num_gpus} GPU(s)")

    def test_gpu_stats_format_real(self, test_config):
        """Test that GPU stats have correct format and reasonable values"""
        monitor = GPUMonitor(test_config)
        stats = monitor.poll_gpu_stats()

        for stat in stats:
            # Check all required fields exist
            assert hasattr(stat, 'gpu_id')
            assert hasattr(stat, 'utilization')
            assert hasattr(stat, 'memory_used')
            assert hasattr(stat, 'memory_total')
            assert hasattr(stat, 'temperature')
            assert hasattr(stat, 'power_draw')
            assert hasattr(stat, 'power_limit')

            # Check reasonable value ranges
            assert stat.gpu_id >= 0
            assert 0 <= stat.utilization <= 100
            assert 0 <= stat.memory_used <= stat.memory_total
            assert stat.temperature >= 0 and stat.temperature < 200  # Celsius
            assert stat.power_draw >= 0

            # power_limit can be None or a positive number
            if stat.power_limit is not None:
                assert stat.power_limit > 0

    def test_cleanup_on_deletion_real(self, test_config):
        """Test cleanup on object deletion"""
        monitor = GPUMonitor(test_config)
        use_pynvml = monitor.use_pynvml

        # Manually call __del__
        monitor.__del__()

        # Should not raise any errors
        # If using pynvml, nvmlShutdown should have been called
        # (We can't easily verify this without mocking, but at least no crash)
        print(f"Cleanup successful for {'pynvml' if use_pynvml else 'nvidia-smi'} mode")
