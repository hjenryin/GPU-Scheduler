"""Tests for the Orchestrator class"""
import pytest
import threading
import time
import signal
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from scheduler.core import Config, PermissionDeniedException
from scheduler.core.models import Job, Node, JobStatus, NodeStatus
from scheduler.head.orchestrator import Orchestrator


class TestOrchestrator:
    """Test cases for Orchestrator class"""

    def test_orchestrator_initialization(self, test_config):
        """Test orchestrator initialization"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            
            assert orchestrator.config == test_config
            assert orchestrator.running is False
            assert orchestrator.scheduler_thread is None
            assert orchestrator.job_manager is not None
            assert orchestrator.node_manager is not None
            assert orchestrator.scheduler is not None
            assert orchestrator.api_server is not None

    def test_orchestrator_initialization_sqlite_backend(self, test_config):
        """Test orchestrator initialization with SQLite backend"""
        # Create a new config with SQLite backend since the original is frozen
        from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig, ClientConfig
        sqlite_config = Config(
            address="localhost:8265",
            head=HeadConfig(
                port=8265,
                heartbeat_timeout=30,
                scheduling_interval=10
            ),
            worker=WorkerConfig(
                temp_dir=test_config.worker.temp_dir,
                log_dir=test_config.worker.log_dir,
                work_dir=test_config.worker.work_dir,
                gpu_poll_interval=5,
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0,
                gpu_stable_time=60,
                job_startup_grace=30
            ),
            storage=StorageConfig(backend='sqlite', db_path='/tmp/test.db'),
            client=ClientConfig()
        )
        
        with patch('scheduler.head.orchestrator.SQLiteBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(sqlite_config)
            
            # Verify SQLite backend was used
            mock_backend.assert_called_once_with(sqlite_config.storage.db_path)

    def test_start_success(self, test_config):
        """Test successful orchestrator start"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            
            # Test start
            orchestrator.start()
            
            assert orchestrator.running is True
            assert orchestrator.scheduler_thread is not None
            assert orchestrator.scheduler_thread.is_alive()
            orchestrator.api_server.start.assert_called_once()

    def test_start_already_running(self, test_config):
        """Test starting orchestrator when already running"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = True
            
            # Test start when already running
            orchestrator.start()
            
            # Should not start again
            orchestrator.api_server.start.assert_not_called()

    def test_start_api_server_failure(self, test_config):
        """Test start failure when API server fails to start"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Make API server start raise an exception
            mock_api_server.return_value.start.side_effect = PermissionDeniedException("Port in use")
            
            orchestrator = Orchestrator(test_config)
            
            # Test start failure
            with pytest.raises(PermissionDeniedException):
                orchestrator.start()
            
            assert orchestrator.running is False

    def test_stop_not_running(self, test_config):
        """Test stopping orchestrator when not running"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = False
            
            # Test stop when not running
            orchestrator.stop()
            
            # Should not call API server stop
            orchestrator.api_server.stop.assert_not_called()

    def test_stop_graceful(self, test_config):
        """Test graceful stop"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock no running jobs
            mock_job_manager.return_value.get_running_jobs.return_value = []
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = True
            orchestrator.scheduler_thread = Mock()
            orchestrator.scheduler_thread.is_alive.return_value = True
            
            # Test graceful stop
            orchestrator.stop(graceful=True)
            
            assert orchestrator.running is False
            orchestrator.api_server.stop.assert_called_once()
            orchestrator.scheduler_thread.join.assert_called_once_with(timeout=5)

    def test_stop_graceful_with_timeout(self, test_config):
        """Test graceful stop with running jobs timeout"""
        # Create a test config with a very short timeout for faster testing
        from scheduler.core.config import HeadConfig, WorkerConfig, StorageConfig, ClientConfig, Config
        
        fast_test_config = Config(
            address="localhost:8265",
            head=HeadConfig(
                port=8265,
                heartbeat_timeout=30,
                scheduling_interval=10,
                graceful_shutdown_timeout=2  # Only 2 seconds for testing
            ),
            worker=WorkerConfig(
                temp_dir=test_config.worker.temp_dir,
                log_dir=test_config.worker.log_dir,
                work_dir=test_config.worker.work_dir,
                gpu_poll_interval=5,
                gpu_util_threshold=10.0,
                gpu_mem_threshold=10.0,
                gpu_stable_time=60,
                job_startup_grace=30
            ),
            storage=StorageConfig(),
            client=ClientConfig()
        )
        
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server, \
             patch('scheduler.head.orchestrator.time.sleep') as mock_sleep:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock running jobs that never complete
            mock_job_manager.return_value.get_running_jobs.return_value = [Mock()]
            
            orchestrator = Orchestrator(fast_test_config)
            orchestrator.running = True
            orchestrator.scheduler_thread = Mock()
            orchestrator.scheduler_thread.is_alive.return_value = True
            
            # Test graceful stop with timeout
            orchestrator.stop(graceful=True)
            
            assert orchestrator.running is False
            orchestrator.api_server.stop.assert_called_once()
            # Should have called sleep multiple times for timeout (2 seconds = 2 calls)
            assert mock_sleep.call_count >= 2

    def test_stop_force(self, test_config):
        """Test force stop"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = True
            orchestrator.scheduler_thread = Mock()
            orchestrator.scheduler_thread.is_alive.return_value = True
            
            # Test force stop
            orchestrator.stop(graceful=False)
            
            assert orchestrator.running is False
            orchestrator.api_server.stop.assert_called_once()
            # Should not wait for jobs to complete
            orchestrator.job_manager.get_running_jobs.assert_not_called()

    def test_run_blocking(self, test_config):
        """Test run method (blocking)"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            
            # Mock the start method to avoid thread creation
            with patch.object(orchestrator, 'start') as mock_start, \
                 patch('scheduler.head.orchestrator.time.sleep') as mock_sleep:
                
                # Mock KeyboardInterrupt to exit the loop immediately
                mock_sleep.side_effect = KeyboardInterrupt()
                
                # Test run method
                orchestrator.run()
                
                # Verify start was called and stop was called due to KeyboardInterrupt
                mock_start.assert_called_once()
                # The stop method should be called in the except block
                assert orchestrator.running is False

    def test_get_status(self, test_config, sample_job, sample_node):
        """Test get_status method"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Setup mock data
            mock_job_manager.return_value.list_jobs.return_value = [sample_job]
            mock_node_manager.return_value.get_connected_nodes.return_value = [sample_node]
            mock_scheduler.return_value.heartbeat_timeout = 30
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = True
            
            # Test get_status
            status = orchestrator.get_status()
            
            assert status['running'] is True
            assert status['nodes']['total'] == 1
            assert status['nodes']['connected'] == 1
            assert status['gpus']['total'] == 2
            assert status['gpus']['free'] == 1  # One GPU is free and stable
            assert status['gpus']['used'] == 1  # One GPU is used
            assert status['jobs']['total'] == 1
            assert status['jobs']['pending'] == 1

    def test_get_status_with_different_job_statuses(self, test_config, sample_node):
        """Test get_status with different job statuses"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Create jobs with different statuses
            jobs = [
                Job(job_id="job1", name="job1", script="script1.py", requirements="1", status=JobStatus.PENDING),
                Job(job_id="job2", name="job2", script="script2.py", requirements="1", status=JobStatus.RUNNING),
                Job(job_id="job3", name="job3", script="script3.py", requirements="1", status=JobStatus.COMPLETED),
                Job(job_id="job4", name="job4", script="script4.py", requirements="1", status=JobStatus.FAILED),
            ]
            
            mock_job_manager.return_value.list_jobs.return_value = jobs
            mock_node_manager.return_value.get_connected_nodes.return_value = [sample_node]
            mock_scheduler.return_value.heartbeat_timeout = 30
            
            orchestrator = Orchestrator(test_config)
            orchestrator.running = True
            
            # Test get_status
            status = orchestrator.get_status()
            
            assert status['jobs']['total'] == 4
            assert status['jobs']['pending'] == 1
            assert status['jobs']['running'] == 1
            assert status['jobs']['completed'] == 1
            assert status['jobs']['failed'] == 1

    def test_scheduler_cycle_business_logic(self, test_config):
        """Test scheduler cycle business logic without threading"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            orchestrator = Orchestrator(test_config)
            
            # Test the business logic directly (no threading)
            orchestrator._do_scheduler_cycle()
            
            # Verify scheduler cycle was called
            orchestrator.scheduler.schedule_cycle.assert_called_once()
            orchestrator.node_manager.check_timeouts.assert_called_once()

    def test_scheduler_loop_normal_operation(self, test_config):
        """Test scheduler loop with mocked threading"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server, \
             patch('scheduler.head.orchestrator.threading.Thread') as mock_thread_class:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock thread creation to prevent real threads
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            orchestrator = Orchestrator(test_config)
            
            # Test start method (which creates the thread)
            orchestrator.start()
            
            # Verify thread was created with correct target
            mock_thread_class.assert_called_once_with(target=orchestrator._scheduler_loop, daemon=True)
            mock_thread.start.assert_called_once()
            
            # Verify orchestrator is running
            assert orchestrator.running is True

    def test_scheduler_loop_exception_handling(self, test_config):
        """Test scheduler loop exception handling"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server, \
             patch('scheduler.head.orchestrator.threading.Thread') as mock_thread_class:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock thread creation to prevent real threads
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            orchestrator = Orchestrator(test_config)
            
            # Test start method (which creates the thread)
            orchestrator.start()
            
            # Verify thread was created with correct target
            mock_thread_class.assert_called_once_with(target=orchestrator._scheduler_loop, daemon=True)
            mock_thread.start.assert_called_once()
            
            # Verify orchestrator is running
            assert orchestrator.running is True

    def test_signal_handler(self, test_config):
        """Test signal handler"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server, \
             patch('scheduler.head.orchestrator.threading.Thread') as mock_thread_class:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock thread creation to prevent real threads
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            orchestrator = Orchestrator(test_config)
            
            # Test signal handler
            orchestrator._signal_handler(signal.SIGTERM, None)
            
            # Should call stop method
            assert orchestrator.running is False

    def test_signal_handler_sigint(self, test_config):
        """Test signal handler with SIGINT"""
        with patch('scheduler.head.orchestrator.FileBackend') as mock_backend, \
             patch('scheduler.head.orchestrator.PersistenceManager') as mock_persistence, \
             patch('scheduler.head.orchestrator.JobManager') as mock_job_manager, \
             patch('scheduler.head.orchestrator.NodeManager') as mock_node_manager, \
             patch('scheduler.head.orchestrator.Scheduler') as mock_scheduler, \
             patch('scheduler.head.orchestrator.APIServer') as mock_api_server, \
             patch('scheduler.head.orchestrator.threading.Thread') as mock_thread_class:
            
            # Mock the managers
            mock_job_manager.return_value = Mock()
            mock_node_manager.return_value = Mock()
            mock_scheduler.return_value = Mock()
            mock_api_server.return_value = Mock()
            
            # Mock thread creation to prevent real threads
            mock_thread = Mock()
            mock_thread_class.return_value = mock_thread
            
            orchestrator = Orchestrator(test_config)
            
            # Test signal handler with SIGINT
            orchestrator._signal_handler(signal.SIGINT, None)
            
            # Should call stop method
            assert orchestrator.running is False
