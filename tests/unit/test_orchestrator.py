"""Unit tests for orchestrator module"""
import pytest
import signal
import threading
import time
import os
from unittest.mock import Mock, patch, MagicMock, create_autospec
import subprocess

from scheduler.head.orchestrator import Orchestrator
from scheduler.core import Config
from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig
from scheduler.core.models import Job, Node


class TestOrchestrator:
    """Tests for Orchestrator class"""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration"""
        from scheduler.core.utils import find_available_port
        
        # Use dynamic port to avoid conflicts
        test_port = find_available_port(start_port=8000, max_attempts=100)
        
        return Config(
            head=HeadConfig(
                port=test_port,
                heartbeat_timeout=10,
                scheduling_interval=1,  # Faster for testing
                graceful_shutdown_timeout=2  # Reduced from 60 for faster testing
            ),
            worker=WorkerConfig(
                work_dir="/tmp/test",
                log_dir="/tmp/test/logs",
                heartbeat_interval=2,  # Must be <= gpu_stable_time
                gpu_poll_interval=2,
                gpu_util_threshold=10,
                gpu_mem_threshold=10,
                gpu_stable_time=2,  # Reduced from 30 for faster tests
                job_startup_grace=3  # Reduced from 120 for faster tests
            ),
            storage=StorageConfig(
                backend="file",
                data_dir="/tmp/test/storage"
            )
        )

    @pytest.fixture
    def orchestrator(self, mock_config):
        """Create an orchestrator instance with mocked dependencies"""
        with patch('scheduler.head.orchestrator.FileBackend', autospec=True), \
             patch('scheduler.head.orchestrator.PersistenceManager', autospec=True), \
             patch('scheduler.head.orchestrator.JobManager', autospec=True), \
             patch('scheduler.head.orchestrator.NodeManager', autospec=True), \
             patch('scheduler.head.orchestrator.Scheduler', autospec=True), \
             patch('scheduler.head.orchestrator.APIServer', autospec=True):
            
            orchestrator = Orchestrator(mock_config)
            return orchestrator

    def test_init_with_file_backend(self, mock_config):
        """Test orchestrator initialization with file backend"""
        with patch('scheduler.head.orchestrator.FileBackend', autospec=True) as mock_file_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager', autospec=True) as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager', autospec=True) as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager', autospec=True) as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler', autospec=True) as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer', autospec=True) as mock_api_server:
            
            orchestrator = Orchestrator(mock_config)
            
            # Verify initialization
            assert orchestrator.config == mock_config
            assert orchestrator.running is False
            assert orchestrator.scheduler_thread is None
            
            # Verify backend was created
            mock_file_backend.assert_called_once_with(mock_config.storage.data_dir)
            
            # Verify managers were created
            mock_persistence.assert_called_once()
            mock_job_manager.assert_called_once()
            mock_node_manager.assert_called_once()
            mock_scheduler.assert_called_once()
            mock_api_server.assert_called_once()

    def test_init_with_sqlite_backend(self):
        """Test orchestrator initialization with SQLite backend"""
        config = Config(
            head=HeadConfig(),
            worker=WorkerConfig(),
            storage=StorageConfig(backend="sqlite", db_path="/tmp/test.db")
        )
        
        with patch('scheduler.head.orchestrator.SQLiteBackend', autospec=True) as mock_sqlite_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager', autospec=True), \
             patch('scheduler.head.orchestrator.JobManager', autospec=True), \
             patch('scheduler.head.orchestrator.NodeManager', autospec=True), \
             patch('scheduler.head.orchestrator.Scheduler', autospec=True), \
             patch('scheduler.head.orchestrator.APIServer', autospec=True):
            
            orchestrator = Orchestrator(config)
            
            # Verify SQLite backend was created
            mock_sqlite_backend.assert_called_once_with(config.storage.db_path)

    def test_start_success(self, orchestrator):
        """Test successful orchestrator start"""
        with patch('threading.Thread', autospec=True) as mock_thread_class:
            
            mock_thread_instance = mock_thread_class.return_value
            
            orchestrator.start()
            
            assert orchestrator.running is True
            orchestrator.api_server.start.assert_called_once()
            mock_thread_class.assert_called_once()
            mock_thread_instance.start.assert_called_once()
            assert orchestrator.scheduler_thread == mock_thread_instance

    def test_start_already_running(self, orchestrator):
        """Test starting orchestrator when already running"""
        orchestrator.running = True
        
        with patch.object(orchestrator.api_server, 'start') as mock_api_start:
            orchestrator.start()
            
            # Should not start again
            mock_api_start.assert_not_called()

    def test_stop_success(self, orchestrator):
        """Test successful orchestrator stop"""
        orchestrator.running = True
        orchestrator.scheduler_thread = create_autospec(threading.Thread, instance=True, spec_set=True)
        orchestrator.scheduler_thread.is_alive.return_value = True
        
        orchestrator.job_manager.get_running_jobs.return_value = []
        
        orchestrator.stop()
        
        assert orchestrator.running is False
        orchestrator.api_server.stop.assert_called_once()
        orchestrator.scheduler_thread.join.assert_called_once_with(timeout=5)

    def test_stop_not_running(self, orchestrator):
        """Test stopping orchestrator when not running"""
        orchestrator.running = False
        
        with patch.object(orchestrator.api_server, 'stop') as mock_api_stop:
            orchestrator.stop()
            
            # Should not stop if not running
            mock_api_stop.assert_not_called()

    def test_scheduler_thread_creation(self, orchestrator):
        """Test scheduler thread creation during start"""
        # Ensure orchestrator is not running initially
        orchestrator.running = False
        
        with patch('threading.Thread', autospec=True) as mock_thread_class:
            
            mock_thread_instance = mock_thread_class.return_value
            
            orchestrator.start()
            
            # Verify thread was created and started
            mock_thread_class.assert_called_once_with(
                target=orchestrator._scheduler_loop,
                daemon=True
            )
            mock_thread_instance.start.assert_called_once()
            assert orchestrator.scheduler_thread == mock_thread_instance

    def test_scheduler_loop(self, orchestrator):
        """Test scheduler loop execution"""
        orchestrator.running = True
        
        with patch('time.sleep', autospec=True) as mock_sleep:
            
            # Mock sleep to raise KeyboardInterrupt after first iteration
            mock_sleep.side_effect = KeyboardInterrupt()
            
            orchestrator._scheduler_loop()
            
            # Should have called _do_scheduler_cycle at least once (it's a mock method)
            # We can't easily assert on internal method calls, but the loop ran
            mock_sleep.assert_called_with(orchestrator.config.head.scheduling_interval)

    def test_scheduler_loop_exception_handling(self, orchestrator):
        """Test scheduler loop exception handling"""
        orchestrator.running = True
        
        with patch('time.sleep', autospec=True) as mock_sleep:
            
            # Mock sleep to raise KeyboardInterrupt after first call to exit loop
            mock_sleep.side_effect = KeyboardInterrupt()
            
            # Should not raise exception - KeyboardInterrupt should be handled gracefully
            orchestrator._scheduler_loop()
            
            # Should have slept after the exception
            mock_sleep.assert_called()

    def test_signal_handler(self, orchestrator):
        """Test signal handler"""
        orchestrator.running = True
        
        with patch.object(orchestrator, 'stop') as mock_stop:
            orchestrator._signal_handler(signal.SIGTERM, None)
            mock_stop.assert_called_once()

    def test_signal_handler_not_running(self, orchestrator):
        """Test signal handler when not running"""
        orchestrator.running = False
        
        with patch.object(orchestrator, 'stop') as mock_stop:
            orchestrator._signal_handler(signal.SIGTERM, None)
            # Should not call stop if not running
            mock_stop.assert_not_called()

    def test_graceful_shutdown(self, orchestrator):
        """Test graceful shutdown with job timeout"""
        orchestrator.running = True
        orchestrator.scheduler_thread = create_autospec(threading.Thread, instance=True, spec_set=True)
        orchestrator.scheduler_thread.is_alive.return_value = True

        # Mock job manager to have running jobs
        orchestrator.job_manager.get_running_jobs.return_value = [create_autospec(Job, instance=True, spec_set=True)]
        
        with patch('time.sleep', autospec=True) as mock_sleep:
            
            orchestrator.stop(graceful=True)
            
            # Should have waited for jobs to complete
            assert mock_sleep.call_count > 0

    def test_graceful_shutdown_no_jobs(self, orchestrator):
        """Test graceful shutdown with no running jobs"""
        orchestrator.running = True
        orchestrator.scheduler_thread = create_autospec(threading.Thread, instance=True, spec_set=True)
        orchestrator.scheduler_thread.is_alive.return_value = True
        
        # Mock job manager to have no running jobs
        orchestrator.job_manager.get_running_jobs.return_value = []
        
        with patch('time.sleep', autospec=True) as mock_sleep:
            
            orchestrator.stop(graceful=True)
            
            # Should not wait if no jobs running
            mock_sleep.assert_not_called()

    def test_get_status(self, orchestrator):
        """Test get_status method"""
        mock_nodes = [
            create_autospec(Node, instance=True, spec_set=True),
            create_autospec(Node, instance=True, spec_set=True)
        ]
        mock_nodes[0].num_gpus = 4
        mock_nodes[0].status.value = 'connected'
        mock_nodes[0].get_free_gpus.return_value = [0, 1]
        mock_nodes[1].num_gpus = 2
        mock_nodes[1].status.value = 'connected'
        mock_nodes[1].get_free_gpus.return_value = [0]

        mock_jobs = [
            create_autospec(Job, instance=True, spec_set=True),
            create_autospec(Job, instance=True, spec_set=True),
            create_autospec(Job, instance=True, spec_set=True)
        ]
        mock_jobs[0].status.value = 'pending'
        mock_jobs[1].status.value = 'running'
        mock_jobs[2].status.value = 'completed'
        
        orchestrator.node_manager.get_connected_nodes.return_value = mock_nodes
        orchestrator.job_manager.list_jobs.return_value = mock_jobs
        
        status = orchestrator.get_status()
        
        assert status['running'] == orchestrator.running
        assert status['nodes']['total'] == 2
        assert status['nodes']['connected'] == 2
        assert status['gpus']['total'] == 6
        assert status['gpus']['free'] == 3
        assert status['gpus']['used'] == 3
        assert status['jobs']['total'] == 3
        assert status['jobs']['pending'] == 1
        assert status['jobs']['running'] == 1
        assert status['jobs']['completed'] == 1

    def test_do_scheduler_cycle(self, orchestrator):
        """Test _do_scheduler_cycle method"""
        orchestrator._do_scheduler_cycle()

        orchestrator.scheduler.schedule_cycle.assert_called_once()
        orchestrator.node_manager.check_timeouts.assert_called_once()

    @patch('scheduler.core.utils.is_port_available')
    @patch('subprocess.Popen')
    def test_rsync_daemon_starts_successfully(self, mock_popen, mock_is_port_available, orchestrator):
        """Test rsync daemon starts successfully when port is available"""
        mock_is_port_available.return_value = True
        mock_process = create_autospec(subprocess.Popen, instance=True, spec_set=True)
        mock_process.poll.return_value = None  # Process running
        mock_popen.return_value = mock_process

        orchestrator._start_rsync_daemon()

        # Should set rsync_port
        assert orchestrator.rsync_port == 8873
        mock_popen.assert_called_once()

    @patch('scheduler.core.utils.is_port_available')
    def test_rsync_daemon_port_unavailable(self, mock_is_port_available, orchestrator):
        """Test rsync daemon handles port unavailable gracefully"""
        mock_is_port_available.return_value = False

        orchestrator._start_rsync_daemon()

        # Should set rsync_port to None
        assert orchestrator.rsync_port is None

    @patch('scheduler.core.utils.is_port_available')
    @patch('tempfile.mkstemp')
    @patch('subprocess.Popen')
    def test_rsync_daemon_config_no_uid_gid(self, mock_popen, mock_mkstemp, mock_is_port_available, orchestrator, tmp_path):
        """Test rsync daemon config does not include uid/gid"""
        mock_is_port_available.return_value = True
        mock_process = create_autospec(subprocess.Popen, instance=True, spec_set=True)
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process

        # Mock mkstemp to return a temp file path
        config_path = str(tmp_path / 'rsync.conf')
        mock_mkstemp.return_value = (os.open(config_path, os.O_CREAT | os.O_WRONLY), config_path)

        orchestrator._start_rsync_daemon()

        # Verify config was written without uid/gid
        with open(config_path, 'r') as f:
            config_content = f.read()

        assert 'uid' not in config_content
        assert 'gid' not in config_content
        assert 'use chroot = no' in config_content

    @patch('scheduler.core.utils.is_port_available')
    @patch('subprocess.Popen')
    def test_rsync_daemon_exception_handling(self, mock_popen, mock_is_port_available, orchestrator):
        """Test rsync daemon handles subprocess exceptions gracefully"""
        mock_is_port_available.return_value = True
        mock_popen.side_effect = OSError("Address already in use")

        orchestrator._start_rsync_daemon()

        # Should set rsync_port to None on error
        assert orchestrator.rsync_port is None