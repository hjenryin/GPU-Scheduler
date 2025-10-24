"""Tests for file handler functionality"""
import pytest
import os
import tempfile
import shutil
import time
from unittest.mock import Mock, patch

from scheduler.worker.file_handler import FileHandler
from scheduler.core.exceptions import PermissionDeniedException


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

    def test_create_versioned_copy_success(self, test_config, temp_dir):
        """Test creating versioned copy of script"""
        # Create a test script
        script_path = os.path.join(temp_dir, "test_script.py")
        with open(script_path, 'w') as f:
            f.write("print('hello')\n")

        handler = FileHandler(test_config)
        job_id = "job-001"

        versioned_path = handler.create_versioned_copy(script_path, job_id)

        # Check that versioned file exists
        assert os.path.exists(versioned_path)
        assert job_id in versioned_path
        assert "test_script" in versioned_path

        # Check that content was copied
        with open(versioned_path, 'r') as f:
            content = f.read()
        assert content == "print('hello')\n"

    def test_create_versioned_copy_preserves_content(self, test_config, temp_dir):
        """Test that versioned copy preserves file content"""
        script_content = """#!/usr/bin/env python3
import numpy as np

def main():
    print("Training model...")

if __name__ == "__main__":
    main()
"""
        script_path = os.path.join(temp_dir, "train.py")
        with open(script_path, 'w') as f:
            f.write(script_content)

        handler = FileHandler(test_config)
        versioned_path = handler.create_versioned_copy(script_path, "job-002")

        with open(versioned_path, 'r') as f:
            versioned_content = f.read()

        assert versioned_content == script_content

    def test_create_versioned_copy_script_not_found(self, test_config):
        """Test creating versioned copy when script doesn't exist"""
        handler = FileHandler(test_config)

        with pytest.raises(FileNotFoundError):
            handler.create_versioned_copy("/nonexistent/script.py", "job-001")

    def test_create_versioned_copy_different_jobs_different_names(self, test_config, temp_dir):
        """Test that different job IDs produce different versioned filenames"""
        script_path = os.path.join(temp_dir, "script.py")
        with open(script_path, 'w') as f:
            f.write("print('test')\n")

        handler = FileHandler(test_config)

        versioned1 = handler.create_versioned_copy(script_path, "job-001")
        versioned2 = handler.create_versioned_copy(script_path, "job-002")

        assert versioned1 != versioned2
        assert "job-001" in versioned1
        assert "job-002" in versioned2
        assert os.path.exists(versioned1)
        assert os.path.exists(versioned2)

    @patch('shutil.copy2')
    def test_create_versioned_copy_permission_error(self, mock_copy, test_config, temp_dir):
        """Test handling of permission errors during copy"""
        script_path = os.path.join(temp_dir, "script.py")
        with open(script_path, 'w') as f:
            f.write("print('test')\n")

        mock_copy.side_effect = PermissionError("Permission denied")

        handler = FileHandler(test_config)

        with pytest.raises(PermissionDeniedException):
            handler.create_versioned_copy(script_path, "job-001")

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

    def test_cleanup_versioned_files_removes_old_files(self, test_config, temp_dir):
        """Test cleanup removes old versioned files"""
        handler = FileHandler(test_config)

        # Create some old files
        old_file1 = os.path.join(handler.work_dir, "old_script_job-001.py")
        old_file2 = os.path.join(handler.work_dir, "old_script_job-002.py")

        with open(old_file1, 'w') as f:
            f.write("old")
        with open(old_file2, 'w') as f:
            f.write("old")

        # Make them old by modifying their timestamp
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        os.utime(old_file1, (old_time, old_time))
        os.utime(old_file2, (old_time, old_time))

        # Create a new file
        new_file = os.path.join(handler.work_dir, "new_script_job-003.py")
        with open(new_file, 'w') as f:
            f.write("new")

        # Run cleanup with 24 hour threshold
        handler.cleanup_versioned_files(max_age_hours=24)

        # Old files should be deleted
        assert not os.path.exists(old_file1)
        assert not os.path.exists(old_file2)

        # New file should remain
        assert os.path.exists(new_file)

    def test_cleanup_versioned_files_preserves_new_files(self, test_config, temp_dir):
        """Test cleanup preserves new files"""
        handler = FileHandler(test_config)

        # Create some new files
        new_file1 = os.path.join(handler.work_dir, "script1.py")
        new_file2 = os.path.join(handler.work_dir, "script2.py")

        with open(new_file1, 'w') as f:
            f.write("new1")
        with open(new_file2, 'w') as f:
            f.write("new2")

        # Run cleanup
        handler.cleanup_versioned_files(max_age_hours=24)

        # Files should still exist
        assert os.path.exists(new_file1)
        assert os.path.exists(new_file2)

    def test_cleanup_versioned_files_skips_directories(self, test_config, temp_dir):
        """Test cleanup skips directories"""
        handler = FileHandler(test_config)

        # Create a subdirectory
        subdir = os.path.join(handler.work_dir, "subdir")
        os.makedirs(subdir)

        # Make it old
        old_time = time.time() - (25 * 3600)
        os.utime(subdir, (old_time, old_time))

        # Run cleanup
        handler.cleanup_versioned_files(max_age_hours=24)

        # Directory should still exist
        assert os.path.exists(subdir)

    def test_cleanup_versioned_files_custom_threshold(self, test_config, temp_dir):
        """Test cleanup with custom age threshold"""
        handler = FileHandler(test_config)

        # Create a file that's 10 hours old
        medium_age_file = os.path.join(handler.work_dir, "medium_file.py")
        with open(medium_age_file, 'w') as f:
            f.write("test")

        medium_time = time.time() - (10 * 3600)  # 10 hours ago
        os.utime(medium_age_file, (medium_time, medium_time))

        # Cleanup with 5 hour threshold - should delete
        handler.cleanup_versioned_files(max_age_hours=5)
        assert not os.path.exists(medium_age_file)

        # Create another file
        medium_age_file2 = os.path.join(handler.work_dir, "medium_file2.py")
        with open(medium_age_file2, 'w') as f:
            f.write("test")
        os.utime(medium_age_file2, (medium_time, medium_time))

        # Cleanup with 20 hour threshold - should keep
        handler.cleanup_versioned_files(max_age_hours=20)
        assert os.path.exists(medium_age_file2)

    def test_cleanup_versioned_files_handles_errors(self, test_config, temp_dir):
        """Test cleanup handles errors gracefully"""
        handler = FileHandler(test_config)

        # Create a file
        test_file = os.path.join(handler.work_dir, "test.py")
        with open(test_file, 'w') as f:
            f.write("test")

        # Make it old
        old_time = time.time() - (25 * 3600)
        os.utime(test_file, (old_time, old_time))

        # Mock os.remove to raise error
        with patch('os.remove', side_effect=OSError("Cannot delete")):
            # Should not raise, just log warning
            handler.cleanup_versioned_files(max_age_hours=24)

    def test_cleanup_empty_directory(self, test_config, temp_dir):
        """Test cleanup on empty directory"""
        handler = FileHandler(test_config)

        # Should not raise any errors
        handler.cleanup_versioned_files(max_age_hours=24)

    @patch('os.listdir')
    def test_cleanup_directory_error(self, mock_listdir, test_config):
        """Test cleanup handles directory listing errors"""
        mock_listdir.side_effect = OSError("Cannot list directory")

        handler = FileHandler(test_config)

        # Should not raise, just log error
        handler.cleanup_versioned_files(max_age_hours=24)

    def test_work_dir_expansion(self):
        """Test that work_dir expands ~ to home directory"""
        from scheduler.core.config import Config, WorkerConfig

        worker_config = WorkerConfig(work_dir="~/test_work", log_dir="~/test_logs")
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
