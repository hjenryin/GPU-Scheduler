"""Tests for file handler functionality"""
import pytest
import os
import tempfile

from scheduler.worker.file_handler import FileHandler


class TestFileHandler:
    """Tests for FileHandler class"""

    def test_init(self, test_config, temp_dir):
        """Test file handler initialization"""
        handler = FileHandler(test_config)

        assert handler.config == test_config
        assert os.path.exists(handler.work_dir)
        assert os.path.exists(handler.log_dir)

    def test_init_creates_directories(self):
        """Test that init creates work and log directories"""
        from scheduler.core.config import Config, WorkerConfig

        with tempfile.TemporaryDirectory() as temp_dir:
            work_dir = os.path.join(temp_dir, "work")
            log_dir = os.path.join(temp_dir, "logs")

            worker_config = WorkerConfig(work_dir=work_dir, log_dir=log_dir)
            config = Config(worker=worker_config)

            handler = FileHandler(config)

            assert os.path.exists(work_dir)
            assert os.path.exists(log_dir)

    def test_get_job_log_path_stdout(self, test_config):
        """Test getting stdout log path"""
        handler = FileHandler(test_config)
        job_id = "job-001"

        log_path = handler.get_job_log_path(job_id, stderr=False)

        assert job_id in log_path
        assert "stdout" in log_path
        assert log_path.endswith(".log")
        assert handler.log_dir in log_path

    def test_get_job_log_path_stderr(self, test_config):
        """Test getting stderr log path"""
        handler = FileHandler(test_config)
        job_id = "job-002"

        log_path = handler.get_job_log_path(job_id, stderr=True)

        assert job_id in log_path
        assert "stderr" in log_path
        assert log_path.endswith(".log")
        assert handler.log_dir in log_path

    def test_get_job_log_paths_different(self, test_config):
        """Test that stdout and stderr paths are different"""
        handler = FileHandler(test_config)
        job_id = "job-001"

        stdout_path = handler.get_job_log_path(job_id, stderr=False)
        stderr_path = handler.get_job_log_path(job_id, stderr=True)

        assert stdout_path != stderr_path

    def test_get_job_snapshot_dir(self, test_config):
        """Test getting job snapshot directory"""
        handler = FileHandler(test_config)
        job_id = "job-001"

        snapshot_dir = handler.get_job_snapshot_dir(job_id)

        assert job_id in snapshot_dir
        assert "snapshot" in snapshot_dir
        assert handler.work_dir in snapshot_dir
        # Directory should be created
        assert os.path.exists(snapshot_dir)

    def test_get_job_snapshot_dir_creates_nested_structure(self, test_config):
        """Test that snapshot dir creates nested directory structure"""
        handler = FileHandler(test_config)
        job_id = "job-002"

        snapshot_dir = handler.get_job_snapshot_dir(job_id)

        # Should be ~/.scheduler/work/job-002/snapshot/
        assert snapshot_dir.endswith(os.path.join(job_id, "snapshot"))
        assert os.path.exists(snapshot_dir)

    def test_work_dir_expansion(self):
        """Test that work_dir expands ~ to home directory"""
        from scheduler.core.config import Config, WorkerConfig

        worker_config = WorkerConfig(work_dir="~/test_work", log_dir="/tmp/test_logs")
        config = Config(worker=worker_config)

        handler = FileHandler(config)

        # Should expand ~
        assert "~" not in handler.work_dir
        assert os.path.expanduser("~") in handler.work_dir or os.path.isabs(handler.work_dir)

    def test_log_dir_expansion(self):
        """Test that log_dir expands ~ to home directory"""
        from scheduler.core.config import Config, WorkerConfig

        worker_config = WorkerConfig(work_dir="~/test_work", log_dir="~/test_logs")
        config = Config(worker=worker_config)

        handler = FileHandler(config)

        # Should expand ~
        assert "~" not in handler.log_dir
        assert os.path.expanduser("~") in handler.log_dir or os.path.isabs(handler.log_dir)
