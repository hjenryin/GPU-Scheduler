"""Tests for GPU monitoring functionality"""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
import threading
import time

from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.core.models import GPUStats


class TestGPUMonitorNvidiaSmi:
    """Tests for GPU monitor using nvidia-smi"""

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    @patch.dict('sys.modules', {'pynvml': None})
    def test_detect_gpus_success(self, mock_run, test_config):
        """Test successful GPU detection"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\nGPU 1: NVIDIA GeForce RTX 3090\n"
        )

        monitor = GPUMonitor(test_config)
        num_gpus = monitor.detect_gpus()

        assert num_gpus == 2
        assert monitor.use_pynvml is False

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_detect_gpus_no_gpus(self, mock_run, test_config):
        """Test GPU detection when no GPUs present"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout=""
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()

            monitor = GPUMonitor(test_config)
            num_gpus = monitor.detect_gpus()

        assert num_gpus == 0

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_detect_gpus_nvidia_smi_not_found(self, mock_run, test_config):
        """Test GPU detection when nvidia-smi not found"""
        mock_run.side_effect = FileNotFoundError("nvidia-smi not found")

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()

            with pytest.raises(RuntimeError, match="nvidia-smi not found"):
                monitor = GPUMonitor(test_config)

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_detect_gpus_timeout(self, mock_run, test_config):
        """Test GPU detection timeout"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("nvidia-smi", 10)

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()

            with pytest.raises(RuntimeError, match="timed out"):
                monitor = GPUMonitor(test_config)

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_poll_gpu_stats_success(self, mock_run, test_config):
        """Test successful GPU stats polling"""
        # Mock detect_gpus call
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\nGPU 1: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()

            monitor = GPUMonitor(test_config)

        # Mock poll_gpu_stats call
        mock_run.return_value = Mock(
            returncode=0,
            stdout="0, 10, 1024, 16384, 45, 50\n1, 95, 15000, 16384, 78, 280\n"
        )

        stats = monitor.poll_gpu_stats()

        assert len(stats) == 2
        assert stats[0].gpu_id == 0
        assert stats[0].utilization == 10.0
        assert stats[0].memory_used == 1024 * 1024 * 1024  # MiB to bytes
        assert stats[0].memory_total == 16384 * 1024 * 1024
        assert stats[0].temperature == 45
        assert stats[0].power_draw == 50

        assert stats[1].gpu_id == 1
        assert stats[1].utilization == 95.0
        assert stats[1].memory_used == 15000 * 1024 * 1024
        assert stats[1].temperature == 78
        assert stats[1].power_draw == 280

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_poll_gpu_stats_empty_lines(self, mock_run, test_config):
        """Test GPU stats polling with empty lines"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        mock_run.return_value = Mock(
            returncode=0,
            stdout="0, 10, 1024, 16384, 45, 50\n\n\n"
        )

        stats = monitor.poll_gpu_stats()
        assert len(stats) == 1

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_poll_gpu_stats_malformed_line(self, mock_run, test_config):
        """Test GPU stats polling with malformed data"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        mock_run.return_value = Mock(
            returncode=0,
            stdout="0, 10, 1024, 16384, 45, 50\nmalformed line\n1, 20, 2048, 16384, 50, 60\n"
        )

        stats = monitor.poll_gpu_stats()
        # Should skip malformed line
        assert len(stats) == 2
        assert stats[0].gpu_id == 0
        assert stats[1].gpu_id == 1

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_poll_gpu_stats_nvidia_smi_error(self, mock_run, test_config):
        """Test GPU stats polling when nvidia-smi fails"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        mock_run.return_value = Mock(
            returncode=1,
            stderr="nvidia-smi error"
        )

        with pytest.raises(RuntimeError, match="nvidia-smi failed"):
            monitor.poll_gpu_stats()

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_monitoring_thread_lifecycle(self, mock_run, test_config):
        """Test starting and stopping monitoring thread"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        # Mock poll_gpu_stats to return test data
        mock_stats = [GPUStats(gpu_id=0, utilization=50.0, memory_used=1024, memory_total=2048, temperature=60, power_draw=100)]
        monitor.poll_gpu_stats = Mock(return_value=mock_stats)

        # Start monitoring
        monitor.start_monitoring()
        assert monitor.monitoring is True
        assert monitor.monitor_thread is not None
        assert monitor.monitor_thread.is_alive()

        # Wait briefly for thread to update stats
        time.sleep(0.1)

        # Check that stats are updated
        stats = monitor.get_latest_stats()
        assert len(stats) > 0

        # Stop monitoring
        monitor.stop_monitoring()
        assert monitor.monitoring is False

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_monitoring_thread_error_handling(self, mock_run, test_config):
        """Test monitoring thread handles errors gracefully"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        # Mock poll_gpu_stats to raise error
        monitor.poll_gpu_stats = Mock(side_effect=RuntimeError("Test error"))

        # Start monitoring (should not crash)
        monitor.start_monitoring()
        time.sleep(0.1)

        # Thread should still be alive despite errors
        assert monitor.monitoring is True

        monitor.stop_monitoring()

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_start_monitoring_already_running(self, mock_run, test_config):
        """Test starting monitoring when already running"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        monitor.poll_gpu_stats = Mock(return_value=[])

        monitor.start_monitoring()
        # Try to start again
        monitor.start_monitoring()  # Should just log warning

        monitor.stop_monitoring()

    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_stop_monitoring_not_running(self, mock_run, test_config):
        """Test stopping monitoring when not running"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="GPU 0: NVIDIA GeForce RTX 3090\n"
        )

        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlInit.side_effect = ImportError()
            monitor = GPUMonitor(test_config)

        # Stop without starting (should just log warning)
        monitor.stop_monitoring()


class TestGPUMonitorPynvml:
    """Tests for GPU monitor using pynvml"""

    def test_init_with_pynvml(self, test_config):
        """Test initialization with pynvml"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlDeviceGetCount.return_value = 2

            monitor = GPUMonitor(test_config)

            assert monitor.use_pynvml is True
            mock_pynvml.nvmlInit.assert_called_once()

    def test_detect_gpus_with_pynvml(self, test_config):
        """Test GPU detection using pynvml"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlDeviceGetCount.return_value = 4

            monitor = GPUMonitor(test_config)
            num_gpus = monitor.detect_gpus()

            assert num_gpus == 4

    def test_poll_with_pynvml_success(self, test_config):
        """Test polling GPU stats with pynvml"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            # Setup mock
            mock_pynvml.nvmlDeviceGetCount.return_value = 1

            mock_handle = Mock()
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

            # Mock utilization
            mock_util = Mock()
            mock_util.gpu = 75
            mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util

            # Mock memory
            mock_mem = Mock()
            mock_mem.used = 8 * 1024 * 1024 * 1024  # 8 GB
            mock_mem.total = 16 * 1024 * 1024 * 1024  # 16 GB
            mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem

            # Mock temperature
            mock_pynvml.nvmlDeviceGetTemperature.return_value = 65
            mock_pynvml.NVML_TEMPERATURE_GPU = 0

            # Mock power
            mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 250000  # 250W in mW

            monitor = GPUMonitor(test_config)
            stats = monitor.poll_gpu_stats()

            assert len(stats) == 1
            assert stats[0].gpu_id == 0
            assert stats[0].utilization == 75.0
            assert stats[0].memory_used == 8 * 1024 * 1024 * 1024
            assert stats[0].memory_total == 16 * 1024 * 1024 * 1024
            assert stats[0].temperature == 65
            assert stats[0].power_draw == 250

    def test_poll_with_pynvml_temperature_error(self, test_config):
        """Test polling when temperature reading fails"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlDeviceGetCount.return_value = 1

            mock_handle = Mock()
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

            mock_util = Mock()
            mock_util.gpu = 50
            mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util

            mock_mem = Mock()
            mock_mem.used = 1024
            mock_mem.total = 2048
            mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem

            # Temperature fails
            mock_pynvml.nvmlDeviceGetTemperature.side_effect = Exception("Temperature error")

            # Power succeeds
            mock_pynvml.nvmlDeviceGetPowerUsage.return_value = 100000

            monitor = GPUMonitor(test_config)
            stats = monitor.poll_gpu_stats()

            assert len(stats) == 1
            assert stats[0].temperature == 0  # Default value on error

    def test_poll_with_pynvml_power_error(self, test_config):
        """Test polling when power reading fails"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlDeviceGetCount.return_value = 1

            mock_handle = Mock()
            mock_pynvml.nvmlDeviceGetHandleByIndex.return_value = mock_handle

            mock_util = Mock()
            mock_util.gpu = 50
            mock_pynvml.nvmlDeviceGetUtilizationRates.return_value = mock_util

            mock_mem = Mock()
            mock_mem.used = 1024
            mock_mem.total = 2048
            mock_pynvml.nvmlDeviceGetMemoryInfo.return_value = mock_mem

            mock_pynvml.nvmlDeviceGetTemperature.return_value = 60
            mock_pynvml.NVML_TEMPERATURE_GPU = 0

            # Power fails
            mock_pynvml.nvmlDeviceGetPowerUsage.side_effect = Exception("Power error")

            monitor = GPUMonitor(test_config)
            stats = monitor.poll_gpu_stats()

            assert len(stats) == 1
            assert stats[0].power_draw == 0  # Default value on error

    def test_cleanup_on_deletion(self, test_config):
        """Test pynvml cleanup on object deletion"""
        with patch('scheduler.worker.gpu_monitor.pynvml') as mock_pynvml:
            mock_pynvml.nvmlDeviceGetCount.return_value = 1

            monitor = GPUMonitor(test_config)
            assert monitor.use_pynvml is True

            # Manually call __del__
            monitor.__del__()

            mock_pynvml.nvmlShutdown.assert_called_once()
