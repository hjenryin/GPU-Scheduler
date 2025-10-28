"""Tests for the PersistenceManager class"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from scheduler.storage import StorageBackend

from scheduler.core import Config
from scheduler.core.models import Job, Node, JobStatus, NodeStatus, JobRequirement
from scheduler.head.persistence import PersistenceManager


class TestPersistenceManager:
    """Test cases for PersistenceManager class"""

    def test_persistence_manager_initialization(self, test_config):
        """Test persistence manager initialization"""
        mock_backend = Mock(spec_set=StorageBackend)
        
        persistence = PersistenceManager(mock_backend, test_config)
        
        assert persistence.backend == mock_backend
        assert persistence.config == test_config

    def test_save_job_success(self, test_config, sample_job):
        """Test successful job save"""
        mock_backend = Mock(spec_set=StorageBackend)
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test save job
        persistence.save_job(sample_job)
        
        mock_backend.save_job.assert_called_once_with(sample_job)

    def test_save_job_failure(self, test_config, sample_job):
        """Test job save failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.save_job.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test save job failure
        with pytest.raises(Exception) as exc_info:
            persistence.save_job(sample_job)
        
        assert "Database error" in str(exc_info.value)
        mock_backend.save_job.assert_called_once_with(sample_job)

    def test_load_job_success(self, test_config, sample_job):
        """Test successful job load"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_job.return_value = sample_job
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load job
        result = persistence.load_job("job-001")
        
        assert result == sample_job
        mock_backend.load_job.assert_called_once_with("job-001")

    def test_load_job_not_found(self, test_config):
        """Test job load when not found"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_job.return_value = None
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load job not found
        result = persistence.load_job("nonexistent-job")
        
        assert result is None
        mock_backend.load_job.assert_called_once_with("nonexistent-job")

    def test_load_job_failure(self, test_config):
        """Test job load failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_job.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load job failure
        result = persistence.load_job("job-001")
        
        assert result is None
        mock_backend.load_job.assert_called_once_with("job-001")

    def test_load_all_jobs_success(self, test_config, sample_job):
        """Test successful load all jobs"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_jobs.return_value = [sample_job]
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all jobs
        result = persistence.load_all_jobs()
        
        assert result == [sample_job]
        mock_backend.load_all_jobs.assert_called_once()

    def test_load_all_jobs_empty(self, test_config):
        """Test load all jobs when empty"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_jobs.return_value = []
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all jobs empty
        result = persistence.load_all_jobs()
        
        assert result == []
        mock_backend.load_all_jobs.assert_called_once()

    def test_load_all_jobs_failure(self, test_config):
        """Test load all jobs failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_jobs.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all jobs failure
        result = persistence.load_all_jobs()
        
        assert result == []
        mock_backend.load_all_jobs.assert_called_once()

    def test_delete_job_success(self, test_config):
        """Test successful job deletion"""
        mock_backend = Mock(spec_set=StorageBackend)
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test delete job
        persistence.delete_job("job-001")
        
        mock_backend.delete_job.assert_called_once_with("job-001")

    def test_delete_job_failure(self, test_config):
        """Test job deletion failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.delete_job.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test delete job failure
        with pytest.raises(Exception) as exc_info:
            persistence.delete_job("job-001")
        
        assert "Database error" in str(exc_info.value)
        mock_backend.delete_job.assert_called_once_with("job-001")

    def test_save_node_success(self, test_config, sample_node):
        """Test successful node save"""
        mock_backend = Mock(spec_set=StorageBackend)
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test save node
        persistence.save_node(sample_node)
        
        mock_backend.save_node.assert_called_once_with(sample_node)

    def test_save_node_failure(self, test_config, sample_node):
        """Test node save failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.save_node.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test save node failure
        with pytest.raises(Exception) as exc_info:
            persistence.save_node(sample_node)
        
        assert "Database error" in str(exc_info.value)
        mock_backend.save_node.assert_called_once_with(sample_node)

    def test_load_node_success(self, test_config, sample_node):
        """Test successful node load"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_node.return_value = sample_node
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load node
        result = persistence.load_node("gpu1")
        
        assert result == sample_node
        mock_backend.load_node.assert_called_once_with("gpu1")

    def test_load_node_not_found(self, test_config):
        """Test node load when not found"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_node.return_value = None
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load node not found
        result = persistence.load_node("nonexistent-node")
        
        assert result is None
        mock_backend.load_node.assert_called_once_with("nonexistent-node")

    def test_load_node_failure(self, test_config):
        """Test node load failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_node.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load node failure
        result = persistence.load_node("gpu1")
        
        assert result is None
        mock_backend.load_node.assert_called_once_with("gpu1")

    def test_load_all_nodes_success(self, test_config, sample_node):
        """Test successful load all nodes"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_nodes.return_value = [sample_node]
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all nodes
        result = persistence.load_all_nodes()
        
        assert result == [sample_node]
        mock_backend.load_all_nodes.assert_called_once()

    def test_load_all_nodes_empty(self, test_config):
        """Test load all nodes when empty"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_nodes.return_value = []
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all nodes empty
        result = persistence.load_all_nodes()
        
        assert result == []
        mock_backend.load_all_nodes.assert_called_once()

    def test_load_all_nodes_failure(self, test_config):
        """Test load all nodes failure"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_nodes.side_effect = Exception("Database error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test load all nodes failure
        result = persistence.load_all_nodes()
        
        assert result == []
        mock_backend.load_all_nodes.assert_called_once()

    def test_checkpoint(self, test_config):
        """Test checkpoint method"""
        mock_backend = Mock(spec_set=StorageBackend)
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test checkpoint
        persistence.checkpoint()
        
        # Checkpoint is a no-op for simple backends
        # Just verify it doesn't raise any exceptions
        assert True

    def test_multiple_operations(self, test_config, sample_job, sample_node):
        """Test multiple persistence operations"""
        mock_backend = Mock(spec_set=StorageBackend)
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test multiple operations
        persistence.save_job(sample_job)
        persistence.save_node(sample_node)
        
        loaded_job = persistence.load_job("job-001")
        loaded_node = persistence.load_node("gpu1")
        
        all_jobs = persistence.load_all_jobs()
        all_nodes = persistence.load_all_nodes()
        
        persistence.delete_job("job-001")
        persistence.checkpoint()
        
        # Verify all operations were called
        mock_backend.save_job.assert_called_once_with(sample_job)
        mock_backend.save_node.assert_called_once_with(sample_node)
        mock_backend.load_job.assert_called_once_with("job-001")
        mock_backend.load_node.assert_called_once_with("gpu1")
        mock_backend.load_all_jobs.assert_called_once()
        mock_backend.load_all_nodes.assert_called_once()
        mock_backend.delete_job.assert_called_once_with("job-001")

    def test_error_logging(self, test_config, sample_job):
        """Test error logging in persistence operations"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.save_job.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            with pytest.raises(Exception):
                persistence.save_job(sample_job)
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to save job" in error_call
            assert "job-001" in error_call
            assert "Test error" in error_call

    def test_load_job_error_logging(self, test_config):
        """Test error logging in load_job"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_job.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            result = persistence.load_job("job-001")
            
            assert result is None
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load job" in error_call
            assert "job-001" in error_call
            assert "Test error" in error_call

    def test_load_all_jobs_error_logging(self, test_config):
        """Test error logging in load_all_jobs"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_jobs.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            result = persistence.load_all_jobs()
            
            assert result == []
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load all jobs" in error_call
            assert "Test error" in error_call

    def test_delete_job_error_logging(self, test_config):
        """Test error logging in delete_job"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.delete_job.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            with pytest.raises(Exception):
                persistence.delete_job("job-001")
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to delete job" in error_call
            assert "job-001" in error_call
            assert "Test error" in error_call

    def test_save_node_error_logging(self, test_config, sample_node):
        """Test error logging in save_node"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.save_node.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            with pytest.raises(Exception):
                persistence.save_node(sample_node)
            
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to save node" in error_call
            assert "gpu1" in error_call
            assert "Test error" in error_call

    def test_load_node_error_logging(self, test_config):
        """Test error logging in load_node"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_node.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            result = persistence.load_node("gpu1")
            
            assert result is None
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load node" in error_call
            assert "gpu1" in error_call
            assert "Test error" in error_call

    def test_load_all_nodes_error_logging(self, test_config):
        """Test error logging in load_all_nodes"""
        mock_backend = Mock(spec_set=StorageBackend)
        mock_backend.load_all_nodes.side_effect = Exception("Test error")
        persistence = PersistenceManager(mock_backend, test_config)
        
        # Test that errors are logged
        with patch('scheduler.head.persistence.logger', autospec=True) as mock_logger:
            result = persistence.load_all_nodes()
            
            assert result == []
            # Verify error was logged
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args[0][0]
            assert "Failed to load all nodes" in error_call
            assert "Test error" in error_call
