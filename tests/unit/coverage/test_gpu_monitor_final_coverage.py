"""Final tests for gpu_monitor.py to reach 90%+ coverage"""
import os
import pytest
import subprocess
from unittest.mock import Mock, patch, MagicMock

from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.core import Config
from scheduler.core.config import WorkerConfig


class TestGPUMonitorFinalCoverage:
    """Tests to cover the last missing lines in gpu_monitor.py"""

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

    def test_init_with_pynvml_success(self, test_config):
        """Test initialization when pynvml is available and succeeds (lines 41-43)"""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit = MagicMock()
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=2)
        mock_pynvml.nvmlShutdown = MagicMock()
        
        with patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            with patch.object(GPUMonitor, 'detect_gpus', return_value=2):
                monitor = GPUMonitor(test_config)
                
                assert monitor.use_pynvml == True
                assert monitor.pynvml is mock_pynvml
                mock_pynvml.nvmlInit.assert_called_once()

    def test_init_with_gpu_detection_failure(self, test_config):
        """Test initialization when GPU detection fails (lines 52-54)"""
        with patch.dict('os.environ', {'SCHEDULER_TEST_MODE': '0'}):
            with patch('scheduler.worker.gpu_monitor.subprocess.run') as mock_run:
                # Make nvidia-smi fail
                mock_result = Mock(spec=subprocess.CompletedProcess)
                mock_result.returncode = 1
                mock_result.stdout = ""
                mock_run.return_value = mock_result
                
                with pytest.raises(RuntimeError, match="Failed to detect GPUs"):
                    GPUMonitor(test_config)

    def test_poll_nvidia_smi_value_error_in_power_draw(self, test_config):
        """Test nvidia-smi polling with ValueError in power draw parsing (lines 237-238)"""
        with patch.dict('os.environ', {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.use_pynvml = False
            
            with patch('scheduler.worker.gpu_monitor.subprocess.run') as mock_run:
                # Return data with unparseable power draw
                mock_result = Mock(spec=subprocess.CompletedProcess)
                mock_result.returncode = 0
                mock_result.stdout = "0, 50, 1024, 8192, 0, invalid_value, 200\n"
                mock_run.return_value = mock_result
                
                stats = monitor.poll_gpu_stats()
                
                # Should handle ValueError gracefully and set power_draw to 0
                assert len(stats) == 1
                assert stats[0].power_draw == 0

    def test_poll_nvidia_smi_attribute_error_in_power_draw(self, test_config):
        """Test nvidia-smi polling with AttributeError in power draw parsing (line 237-238)"""
        with patch.dict('os.environ', {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.use_pynvml = False
            
            with patch('scheduler.worker.gpu_monitor.subprocess.run') as mock_run:
                # Simulate AttributeError by returning None for power draw field
                mock_result = Mock(spec=subprocess.CompletedProcess)
                mock_result.returncode = 0
                # Create a line where parts[5] could cause AttributeError
                mock_result.stdout = "0, 50, 1024, 8192, 0, , 200\n"
                mock_run.return_value = mock_result
                
                stats = monitor.poll_gpu_stats()
                
                # Should handle exception gracefully
                assert len(stats) == 1

    def test_poll_nvidia_smi_value_error_in_power_limit(self, test_config):
        """Test nvidia-smi polling with ValueError in power limit parsing (lines 243-244)"""
        with patch.dict('os.environ', {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.use_pynvml = False
            
            with patch('scheduler.worker.gpu_monitor.subprocess.run') as mock_run:
                # Return data with unparseable power limit
                mock_result = Mock(spec=subprocess.CompletedProcess)
                mock_result.returncode = 0
                mock_result.stdout = "0, 50, 1024, 8192, 0, 150, invalid_limit\n"
                mock_run.return_value = mock_result
                
                stats = monitor.poll_gpu_stats()
                
                # Should handle ValueError gracefully and set power_limit to None
                assert len(stats) == 1
                assert stats[0].power_limit is None

    def test_poll_nvidia_smi_attribute_error_in_power_limit(self, test_config):
        """Test nvidia-smi polling with AttributeError in power limit parsing (lines 243-244)"""
        with patch.dict('os.environ', {'SCHEDULER_TEST_MODE': '1'}):
            monitor = GPUMonitor(test_config)
            monitor.use_pynvml = False
            
            with patch('scheduler.worker.gpu_monitor.subprocess.run') as mock_run:
                # Return data that could cause AttributeError
                mock_result = Mock(spec=subprocess.CompletedProcess)
                mock_result.returncode = 0
                mock_result.stdout = "0, 50, 1024, 8192, 0, 150, \n"
                mock_run.return_value = mock_result
                
                stats = monitor.poll_gpu_stats()
                
                # Should handle exception gracefully
                assert len(stats) == 1

    def test_cleanup_pynvml_shutdown_exception(self, test_config):
        """Test cleanup when pynvml shutdown fails (lines 329-330)"""
        mock_pynvml = MagicMock()
        mock_pynvml.nvmlInit = MagicMock()
        mock_pynvml.nvmlDeviceGetCount = MagicMock(return_value=1)
        mock_pynvml.nvmlShutdown = MagicMock(side_effect=Exception("Shutdown failed"))
        
        with patch.dict('sys.modules', {'pynvml': mock_pynvml}):
            with patch.object(GPUMonitor, 'detect_gpus', return_value=1):
                monitor = GPUMonitor(test_config)
                monitor.use_pynvml = True
                monitor.pynvml = mock_pynvml
                
                # Should not raise exception during cleanup (__del__)
                # Trigger __del__ by deleting the monitor
                del monitor
                
                mock_pynvml.nvmlShutdown.assert_called_once()
