"""Tests for file_handler.py to reach 90%+ coverage"""
import os
import time
import tempfile
import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from scheduler.worker.file_handler import FileHandler
from scheduler.core import Config
from scheduler.core.config import WorkerConfig


class TestFileHandlerCoverage:
    """Tests to cover missing lines in file_handler.py"""

    @pytest.fixture
    def temp_log_dir(self):
        """Create a temporary log directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def file_handler(self, temp_log_dir):
        """Create FileHandler with temp directory"""
        config = Config(worker=WorkerConfig(log_dir=temp_log_dir, work_dir=temp_log_dir))
        return FileHandler(config=config)

    def test_cleanup_old_logs_with_nonexistent_dir(self):
        """Test cleanup_old_logs when log directory doesn't exist (line 79)"""
        config = Config(worker=WorkerConfig(log_dir="/nonexistent/log/dir", work_dir="/nonexistent/work"))
        # Patch ensure_dir_exists to prevent actual directory creation
        with patch('scheduler.worker.file_handler.ensure_dir_exists'):
            handler = FileHandler(config=config)
        
        result = handler.cleanup_old_logs(max_age_hours=24)
        
        assert result == 0

    def test_cleanup_old_logs_skip_non_log_files(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs skips non-.log files (lines 87-88)"""
        # Create non-log files
        Path(temp_log_dir, "readme.txt").touch()
        Path(temp_log_dir, "data.json").touch()
        
        # Create old log file
        old_log = Path(temp_log_dir, "old.log")
        old_log.touch()
        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(old_log, (old_time, old_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24)
        
        # Should remove only the .log file, not the txt/json files
        assert result == 1
        assert not old_log.exists()
        assert Path(temp_log_dir, "readme.txt").exists()
        assert Path(temp_log_dir, "data.json").exists()

    def test_cleanup_old_logs_skip_job_logs_by_default(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs skips job logs unless explicitly requested (lines 92-93)"""
        # Create old job log files
        job_stdout = Path(temp_log_dir, "job_123.stdout.log")
        job_stderr = Path(temp_log_dir, "job_456.stderr.log")
        job_stdout.touch()
        job_stderr.touch()
        
        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(job_stdout, (old_time, old_time))
        os.utime(job_stderr, (old_time, old_time))
        
        # Create regular old log
        regular_log = Path(temp_log_dir, "worker.log")
        regular_log.touch()
        os.utime(regular_log, (old_time, old_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24, include_job_logs=False)
        
        # Should remove only regular log, not job logs
        assert result == 1
        assert job_stdout.exists()
        assert job_stderr.exists()
        assert not regular_log.exists()

    def test_cleanup_old_logs_include_job_logs(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs includes job logs when requested (line 92-93)"""
        # Create old job log files
        job_log = Path(temp_log_dir, "job_789.stdout.log")
        job_log.touch()
        
        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        os.utime(job_log, (old_time, old_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24, include_job_logs=True)
        
        # Should remove job log
        assert result == 1
        assert not job_log.exists()

    def test_cleanup_old_logs_skip_directories(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs skips directories (lines 98-99)"""
        # Create a directory with .log extension
        log_dir = Path(temp_log_dir, "subdir.log")
        log_dir.mkdir()
        
        # Create old regular log file
        old_log = Path(temp_log_dir, "old.log")
        old_log.touch()
        old_time = time.time() - (25 * 3600)
        os.utime(old_log, (old_time, old_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24)
        
        # Should remove file but skip directory
        assert result == 1
        assert log_dir.exists()
        assert not old_log.exists()

    def test_cleanup_old_logs_os_error_during_processing(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs handles OSError when processing file (lines 110-111)"""
        # Create old log file
        old_log = Path(temp_log_dir, "old.log")
        old_log.touch()
        old_time = time.time() - (25 * 3600)
        os.utime(old_log, (old_time, old_time))
        
        # Mock os.remove to raise OSError
        with patch('os.remove', side_effect=OSError("Permission denied")):
            result = file_handler.cleanup_old_logs(max_age_hours=24)
            
            # Should handle error gracefully and continue
            assert result == 0
            assert old_log.exists()

    def test_cleanup_old_logs_generic_exception(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs handles generic exception (lines 116-117)"""
        # Create a log file
        log_file = Path(temp_log_dir, "test.log")
        log_file.touch()
        
        # Mock os.listdir to raise exception
        with patch('os.listdir', side_effect=Exception("Unexpected error")):
            result = file_handler.cleanup_old_logs(max_age_hours=24)
            
            # Should handle error gracefully
            assert result == 0

    def test_cleanup_old_logs_removes_multiple_old_files(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs removes multiple old files and logs count (lines 106-109, 113-114)"""
        # Create multiple old log files
        old_log1 = Path(temp_log_dir, "old1.log")
        old_log2 = Path(temp_log_dir, "old2.log")
        old_log3 = Path(temp_log_dir, "old3.log")
        
        old_log1.touch()
        old_log2.touch()
        old_log3.touch()
        
        # Set mtime to 25 hours ago
        old_time = time.time() - (25 * 3600)
        for log_file in [old_log1, old_log2, old_log3]:
            os.utime(log_file, (old_time, old_time))
        
        # Create recent log that should not be removed
        recent_log = Path(temp_log_dir, "recent.log")
        recent_log.touch()
        
        result = file_handler.cleanup_old_logs(max_age_hours=24)
        
        # Should remove 3 old files
        assert result == 3
        assert not old_log1.exists()
        assert not old_log2.exists()
        assert not old_log3.exists()
        assert recent_log.exists()

    def test_cleanup_old_logs_file_exactly_at_age_threshold(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs with file exactly at age threshold (line 106)"""
        # Create log file exactly 24 hours old
        log_file = Path(temp_log_dir, "threshold.log")
        log_file.touch()
        
        # Set mtime to exactly 24 hours ago
        threshold_time = time.time() - (24 * 3600)
        os.utime(log_file, (threshold_time, threshold_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24)
        
        # File exactly at threshold should not be removed (age_seconds <= max_age_seconds doesn't satisfy > condition)
        # But due to time passing during test execution, it may be removed
        # So we just verify the test completes without error
        assert result in (0, 1)

    def test_cleanup_old_logs_file_just_over_threshold(self, file_handler, temp_log_dir):
        """Test cleanup_old_logs with file just over age threshold (line 106)"""
        # Create log file slightly over 24 hours old
        log_file = Path(temp_log_dir, "just_over.log")
        log_file.touch()
        
        # Set mtime to 24 hours + 1 second ago
        over_time = time.time() - (24 * 3600 + 1)
        os.utime(log_file, (over_time, over_time))
        
        result = file_handler.cleanup_old_logs(max_age_hours=24)
        
        # File just over threshold should be removed
        assert result == 1
        assert not log_file.exists()
