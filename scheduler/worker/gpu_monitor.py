import logging
import os
import subprocess
import threading
import time
from typing import List, Optional

from scheduler.core import Config, GPUStats

logger = logging.getLogger(__name__)


class GPUMonitor:
    """Monitors GPU status and statistics"""

    def __init__(self, config: Config):
        """
        Initialize GPU monitor.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.use_pynvml = False
        self.use_test_mode = False
        self.latest_stats: List[GPUStats] = []
        self.monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.poll_interval = config.worker.gpu_poll_interval

        # Check for test mode (for E2E tests without real GPUs)
        if os.environ.get('SCHEDULER_TEST_MODE') == '1':
            self.use_test_mode = True
            logger.info("Using test mode for GPU monitoring (mock GPUs)")
            return  # Skip real GPU initialization

        # Try to initialize pynvml
        try:
            import pynvml
            pynvml.nvmlInit()
            self.use_pynvml = True
            self.pynvml = pynvml
            logger.info("Using pynvml for GPU monitoring")
        except (ImportError, Exception) as e:
            logger.warning(f"pynvml not available, falling back to nvidia-smi: {e}")
            self.use_pynvml = False

        # Verify GPU access
        try:
            num_gpus = self.detect_gpus()
            logger.info(f"Detected {num_gpus} GPU(s)")
        except RuntimeError as e:
            logger.error(f"Failed to detect GPUs: {e}")
            raise

    def detect_gpus(self) -> int:
        """
        Auto-detect number of GPUs on this machine.

        Returns:
            Number of GPUs detected

        Raises:
            RuntimeError: If nvidia-smi not available or fails
        """
        if self.use_pynvml:
            try:
                return self.pynvml.nvmlDeviceGetCount()
            except Exception as e:
                raise RuntimeError(f"Failed to detect GPUs via pynvml: {e}")
        else:
            # Use nvidia-smi
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--list-gpus'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0:
                    raise RuntimeError(f"nvidia-smi failed: {result.stderr}")

                # Count lines (each line is a GPU)
                gpu_lines = [line for line in result.stdout.strip().split('\n') if line]
                return len(gpu_lines)
            except FileNotFoundError:
                raise RuntimeError("nvidia-smi not found. Is NVIDIA driver installed?")
            except subprocess.TimeoutExpired:
                raise RuntimeError("nvidia-smi timed out")
            except Exception as e:
                raise RuntimeError(f"Failed to detect GPUs: {e}")

    def poll_gpu_stats(self) -> List[GPUStats]:
        """
        Poll current GPU statistics.

        Returns:
            List of GPUStats for each GPU

        Raises:
            RuntimeError: If polling fails
        """
        if self.use_pynvml:
            try:
                return self._poll_with_pynvml()
            except Exception as e:
                # pynvml can fail in multiprocess environments, fall back to nvidia-smi
                logger.warning(f"pynvml polling failed, falling back to nvidia-smi: {e}")
                self.use_pynvml = False
                return self._poll_with_nvidia_smi()
        else:
            return self._poll_with_nvidia_smi()

    def _poll_with_pynvml(self) -> List[GPUStats]:
        """Poll GPU stats using pynvml."""
        stats = []
        try:
            device_count = self.pynvml.nvmlDeviceGetCount()
            for i in range(device_count):
                handle = self.pynvml.nvmlDeviceGetHandleByIndex(i)

                # Get utilization
                util = self.pynvml.nvmlDeviceGetUtilizationRates(handle)
                utilization = float(util.gpu)

                # Get memory info
                mem_info = self.pynvml.nvmlDeviceGetMemoryInfo(handle)
                memory_used = mem_info.used
                memory_total = mem_info.total

                # Get temperature
                try:
                    temperature = self.pynvml.nvmlDeviceGetTemperature(handle, self.pynvml.NVML_TEMPERATURE_GPU)
                except Exception as e:
                    logger.debug(f"Failed to get GPU {i} temperature: {e}")
                    temperature = 0

                # Get power draw
                try:
                    power_draw = self.pynvml.nvmlDeviceGetPowerUsage(handle) // 1000  # mW to W
                except Exception as e:
                    logger.debug(f"Failed to get GPU {i} power draw: {e}")
                    power_draw = 0

                # Get power limit
                try:
                    power_limit = self.pynvml.nvmlDeviceGetPowerManagementLimit(handle) // 1000  # mW to W
                except Exception as e:
                    logger.debug(f"Failed to get GPU {i} power limit: {e}")
                    power_limit = None  # Display N/A, like nvitop

                # Get running processes on this GPU
                running_job_id = self._get_running_job_id(i)

                stats.append(GPUStats(
                    gpu_id=i,
                    utilization=utilization,
                    memory_used=memory_used,
                    memory_total=memory_total,
                    temperature=temperature,
                    power_draw=power_draw,
                    power_limit=power_limit,
                    running_job_id=running_job_id
                ))

            return stats
        except Exception as e:
            import traceback
            logger.error(f"Full error details: {traceback.format_exc()}")
            raise RuntimeError(f"Failed to poll GPU stats with pynvml: {e}")

    def _get_running_job_id(self, gpu_id: int) -> Optional[str]:
        """Get the job ID of the process currently running on the specified GPU.
        
        Args:
            gpu_id: GPU index
            
        Returns:
            Job ID if a process is running on the GPU, None otherwise
        """
        if not self.use_pynvml:
            return None
            
        try:
            handle = self.pynvml.nvmlDeviceGetHandleByIndex(gpu_id)
            processes = self.pynvml.nvmlDeviceGetComputeRunningProcesses(handle)
            
            if processes:
                # For now, return the PID of the first process
                # In a real implementation, you might want to map this to actual job IDs
                # by checking process names, command lines, or other identifiers
                pid = processes[0].pid
                return f"pid_{pid}"
            return None
            
        except Exception as e:
            logger.debug(f"Failed to get running processes for GPU {gpu_id}: {e}")
            return None

    def _poll_with_nvidia_smi(self) -> List[GPUStats]:
        """Poll GPU stats using nvidia-smi."""
        try:
            # Query format: index, utilization.gpu, memory.used, memory.total, temperature.gpu, power.draw, power.limit
            result = subprocess.run(
                [
                    'nvidia-smi',
                    '--query-gpu=index,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,power.limit',
                    '--format=csv,noheader,nounits'
                ],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RuntimeError(f"nvidia-smi failed: {result.stderr}")

            stats = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 7:
                    continue

                try:
                    gpu_id = int(parts[0])
                    utilization = float(parts[1])
                    memory_used = int(parts[2]) * 1024 * 1024  # MiB to bytes
                    memory_total = int(parts[3]) * 1024 * 1024  # MiB to bytes
                    temperature = int(parts[4])

                    # Power draw and limit may be [N/A] or [Not Supported] on some GPUs
                    try:
                        power_draw = int(float(parts[5].replace('[N/A]', '0').replace('[Not Supported]', '0')))
                    except (ValueError, AttributeError):
                        power_draw = 0

                    try:
                        power_limit_str = parts[6].replace('[N/A]', '').replace('[Not Supported]', '').strip()
                        power_limit = int(float(power_limit_str)) if power_limit_str and power_limit_str != '[]' else None
                    except (ValueError, AttributeError):
                        power_limit = None

                    # Try to get running job ID using nvml if available
                    running_job_id = None
                    if self.use_pynvml:
                        running_job_id = self._get_running_job_id(gpu_id)

                    stats.append(GPUStats(
                        gpu_id=gpu_id,
                        utilization=utilization,
                        memory_used=memory_used,
                        memory_total=memory_total,
                        temperature=temperature,
                        power_draw=power_draw,
                        power_limit=power_limit,
                        running_job_id=running_job_id
                    ))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse nvidia-smi line '{line}': {e}")
                    continue

            return stats
        except FileNotFoundError:
            raise RuntimeError("nvidia-smi not found")
        except subprocess.TimeoutExpired:
            raise RuntimeError("nvidia-smi timed out")
        except Exception as e:
            raise RuntimeError(f"Failed to poll GPU stats: {e}")

    def start_monitoring(self):
        """
        Start background GPU monitoring thread.
        """
        if self.monitoring:
            logger.warning("GPU monitoring is already running")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("GPU monitoring started")

    def stop_monitoring(self):
        """
        Stop background GPU monitoring thread.
        """
        if not self.monitoring:
            logger.warning("GPU monitoring is not running")
            return

        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)

        logger.info("GPU monitoring stopped")

    def get_latest_stats(self) -> List[GPUStats]:
        """
        Get most recent GPU statistics.

        Returns:
            List of latest GPUStats
        """
        return self.latest_stats

    def _monitoring_loop(self):
        """Internal monitoring loop thread."""
        logger.info("GPU monitoring loop started")

        while self.monitoring:
            try:
                self.latest_stats = self.poll_gpu_stats()
            except Exception as e:
                logger.error(f"Error polling GPU stats: {e}")
                # Keep previous stats on error

            time.sleep(self.poll_interval)

        logger.info("GPU monitoring loop stopped")

    def __del__(self):
        """Cleanup on deletion."""
        if self.use_pynvml:
            try:
                self.pynvml.nvmlShutdown()
            except Exception as e:
                logger.warning(f"Failed to shutdown pynvml: {e}")
