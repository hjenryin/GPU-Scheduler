"""Additional tests for gpu_monitor.py to improve coverage to 90%+"""
import os
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock, create_autospec

from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.core import Config, GPUStats
from scheduler.core.config import WorkerConfig


class TestGPUMonitorCoverageImprovements:
    """Tests to cover missing lines in gpu_monitor.py"""

    @pytest.fixture
    def test_config(self):
        """Create test configuration"""
        return Config(
            worker=WorkerConfig(
                gpu_poll_interval=2,
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0
            )
        )

    def test_poll_pynvml_temperature_error(self, test_config):
        """Test poll_gpu_stats when getting temperature fails (lines 134-136)"""
        mock_pynvml = MagicMock()  # Mock pynvml module - external C library interface
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
        mock_handle = Mock()  # Mock NVML device handle - C library opaque pointer
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value=mock_handle)
        
        # Mock memory info
        mock_mem_info = Mock()
        mock_mem_info.used = 1024 * 1024 * 1024  # 1GB
        mock_mem_info.total = 8 * 1024 * 1024 * 1024  # 8GB
        mock_pynvml.nvmlDeviceGetMemoryInfo = MagicMock(return_value=mock_mem_info)
        
        # Mock utilization
        mock_util = Mock()
        mock_util.gpu = 50
        mock_pynvml.nvmlDeviceGetUtilizationRates = MagicMock(return_value=mock_util)
        
        # Mock temperature to raise exception
        mock_pynvml.nvmlDeviceGetTemperature = MagicMock(side_effect=Exception("Temperature read failed"))
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        
        # Mock other metrics
        mock_pynvml.nvmlDeviceGetPowerUsage = MagicMock(return_value=150000)  # 150W in mW
        mock_pynvml.nvmlDeviceGetPowerManagementLimit = MagicMock(return_value=200000)  # 200W in mW
        mock_pynvml.nvmlDeviceGetComputeRunningProcesses = MagicMock(return_value=[])
        
        with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.pynvml = mock_pynvml
            monitor.use_pynvml = True
            monitor.use_test_mode = False
            
            stats = monitor.poll_gpu_stats()
            assert len(stats) == 1
            assert stats[0].temperature == 0  # Should default to 0 on error

    def test_poll_pynvml_power_draw_error(self, test_config):
        """Test poll_gpu_stats when getting power draw fails (lines 141-143)"""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
        mock_handle = Mock()
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value=mock_handle)
        
        # Mock memory info
        mock_mem_info = Mock()
        mock_mem_info.used = 1024 * 1024 * 1024
        mock_mem_info.total = 8 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo = MagicMock(return_value=mock_mem_info)
        
        # Mock utilization
        mock_util = Mock()
        mock_util.gpu = 50
        mock_pynvml.nvmlDeviceGetUtilizationRates = MagicMock(return_value=mock_util)
        
        # Mock temperature
        mock_pynvml.nvmlDeviceGetTemperature = MagicMock(return_value=60)
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        
        # Mock power draw to raise exception
        mock_pynvml.nvmlDeviceGetPowerUsage = MagicMock(side_effect=Exception("Power draw read failed"))
        
        # Mock other metrics
        mock_pynvml.nvmlDeviceGetPowerManagementLimit = MagicMock(return_value=200000)
        mock_pynvml.nvmlDeviceGetComputeRunningProcesses = MagicMock(return_value=[])
        
        with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.pynvml = mock_pynvml
            monitor.use_pynvml = True
            monitor.use_test_mode = False
            
            stats = monitor.poll_gpu_stats()
            assert len(stats) == 1
            assert stats[0].power_draw == 0  # Should default to 0 on error

    def test_poll_pynvml_power_limit_error(self, test_config):
        """Test poll_gpu_stats when getting power limit fails (lines 148-150)"""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
        mock_handle = Mock()
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value=mock_handle)
        
        # Mock memory info
        mock_mem_info = Mock()
        mock_mem_info.used = 1024 * 1024 * 1024
        mock_mem_info.total = 8 * 1024 * 1024 * 1024
        mock_pynvml.nvmlDeviceGetMemoryInfo = MagicMock(return_value=mock_mem_info)
        
        # Mock utilization
        mock_util = Mock()
        mock_util.gpu = 50
        mock_pynvml.nvmlDeviceGetUtilizationRates = MagicMock(return_value=mock_util)
        
        # Mock temperature
        mock_pynvml.nvmlDeviceGetTemperature = MagicMock(return_value=60)
        mock_pynvml.NVML_TEMPERATURE_GPU = 0
        
        # Mock power draw
        mock_pynvml.nvmlDeviceGetPowerUsage = MagicMock(return_value=150000)
        
        # Mock power limit to raise exception
        mock_pynvml.nvmlDeviceGetPowerManagementLimit = MagicMock(side_effect=Exception("Power limit read failed"))
        mock_pynvml.nvmlDeviceGetComputeRunningProcesses = MagicMock(return_value=[])
        
        with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.pynvml = mock_pynvml
            monitor.use_pynvml = True
            monitor.use_test_mode = False
            
            stats = monitor.poll_gpu_stats()
            assert len(stats) == 1
            assert stats[0].power_limit is None  # Should be None on error

    def test_poll_nvidia_smi_error_returncode(self, test_config):
        """Test poll_gpu_stats when nvidia-smi returns error code (line 216)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 1
        mock_result.stderr = "Error: nvidia-smi failed"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                with pytest.raises(RuntimeError, match="nvidia-smi failed"):
                    monitor.poll_gpu_stats()

    def test_poll_nvidia_smi_empty_line(self, test_config):
        """Test poll_gpu_stats with empty lines (line 221)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        # Include empty line
        mock_result.stdout = "0, 50, 1024, 8192, 60, 150, 200\n\n1, 30, 512, 8192, 55, 100, 200\n"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                stats = monitor.poll_gpu_stats()
                assert len(stats) == 2  # Should skip empty line

    def test_poll_nvidia_smi_short_line(self, test_config):
        """Test poll_gpu_stats with short line (line 225)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        # Include line with too few parts
        mock_result.stdout = "0, 50, 1024\n1, 30, 512, 8192, 55, 100, 200\n"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                stats = monitor.poll_gpu_stats()
                assert len(stats) == 1  # Should skip short line

    def test_poll_nvidia_smi_power_draw_not_supported(self, test_config):
        """Test poll_gpu_stats with [Not Supported] power draw (line 237-238)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        mock_result.stdout = "0, 50, 1024, 8192, 60, [Not Supported], 200\n"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                stats = monitor.poll_gpu_stats()
                assert len(stats) == 1
                assert stats[0].power_draw == 0  # Should handle [Not Supported]

    def test_poll_nvidia_smi_power_limit_empty(self, test_config):
        """Test poll_gpu_stats with empty power limit (line 243-244)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        mock_result.stdout = "0, 50, 1024, 8192, 60, 150, []\n"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                stats = monitor.poll_gpu_stats()
                assert len(stats) == 1
                assert stats[0].power_limit is None  # Should be None for []

    def test_poll_nvidia_smi_with_pynvml_for_job_id(self, test_config):
        """Test poll_gpu_stats with nvidia-smi but pynvml available for job ID (line 249)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        mock_result.stdout = "0, 50, 1024, 8192, 60, 150, 200\n"
        
        mock_pynvml = MagicMock()  # Mock pynvml module - external C library interface
        mock_process = Mock()  # Mock NVML process struct - C library data structure
        mock_process.pid = 12345
        mock_pynvml.nvmlDeviceGetComputeRunningProcesses = MagicMock(return_value=[mock_process])
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(return_value=Mock())
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = True  # pynvml available
                monitor.pynvml = mock_pynvml
                monitor.use_test_mode = False
                
                # Override poll to use nvidia-smi path
                stats = monitor._poll_with_nvidia_smi()
                assert len(stats) == 1
                assert stats[0].running_job_id == "pid_12345"

    def test_poll_nvidia_smi_parse_error(self, test_config):
        """Test poll_gpu_stats with unparseable line (line 261-263)"""
        mock_result = Mock()  # Mock subprocess.CompletedProcess - simple data container
        mock_result.returncode = 0
        # Include line with invalid data
        mock_result.stdout = "0, invalid, xyz, 8192, 60, 150, 200\n1, 30, 512, 8192, 55, 100, 200\n"
        
        with patch('subprocess.run', return_value=mock_result, autospec=True):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                stats = monitor.poll_gpu_stats()
                assert len(stats) == 1  # Should skip unparseable line, continue with valid one

    def test_poll_nvidia_smi_file_not_found(self, test_config):
        """Test poll_gpu_stats when nvidia-smi not found (line 268)"""
        with patch('subprocess.run', side_effect=FileNotFoundError("nvidia-smi not found")):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                with pytest.raises(RuntimeError, match="nvidia-smi not found"):
                    monitor.poll_gpu_stats()

    def test_poll_nvidia_smi_timeout(self, test_config):
        """Test poll_gpu_stats when nvidia-smi times out (line 269)"""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired('nvidia-smi', 10)):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                with pytest.raises(RuntimeError, match="nvidia-smi timed out"):
                    monitor.poll_gpu_stats()

    def test_poll_nvidia_smi_generic_exception(self, test_config):
        """Test poll_gpu_stats with generic exception (line 271)"""
        with patch('subprocess.run', side_effect=Exception("Unexpected error")):
            with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = False
                monitor.use_test_mode = False
                
                with pytest.raises(RuntimeError, match="Failed to poll GPU stats"):
                    monitor.poll_gpu_stats()

    def test_get_running_job_id_error(self, test_config):
        """Test _get_running_job_id when exception occurs (line 261-263 alternative path)"""
        mock_pynvml = MagicMock()  # Mock pynvml module - external C library interface
        mock_pynvml.nvmlDeviceGetHandleByIndex = MagicMock(side_effect=Exception("Handle error"))
        
        with patch.dict(os.environ, {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.pynvml = mock_pynvml
            monitor.use_pynvml = True
            monitor.use_test_mode = False
            
            job_id = monitor._get_running_job_id(0)
            assert job_id is None  # Should return None on error
