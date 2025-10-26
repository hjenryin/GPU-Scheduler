"""Unit tests for logging configuration"""
import pytest
import logging
import tempfile
import os
from pathlib import Path

from scheduler.core.logging_config import setup_logging, get_logger


class TestSetupLogging:
    """Tests for setup_logging function"""

    def test_setup_logging_default(self):
        """Test setup_logging with default parameters"""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging()
        
        # Check that handler is added
        assert len(root_logger.handlers) > 0
        assert root_logger.level == logging.INFO

    def test_setup_logging_debug_level(self):
        """Test setup_logging with DEBUG level"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging(log_level="DEBUG")
        
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_warning_level(self):
        """Test setup_logging with WARNING level"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging(log_level="WARNING")
        
        assert root_logger.level == logging.WARNING

    def test_setup_logging_error_level(self):
        """Test setup_logging with ERROR level"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging(log_level="ERROR")
        
        assert root_logger.level == logging.ERROR

    def test_setup_logging_invalid_level_defaults_to_info(self):
        """Test setup_logging with invalid level defaults to INFO"""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        setup_logging(log_level="INVALID_LEVEL")
        
        assert root_logger.level == logging.INFO

    def test_setup_logging_with_log_dir(self):
        """Test setup_logging creates log file when log_dir specified"""
        with tempfile.TemporaryDirectory() as temp_dir:
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            setup_logging(log_level="INFO", log_dir=temp_dir, component="test_component")
            
            # Check log file was created
            log_file = Path(temp_dir) / "test_component.log"
            assert log_file.exists()
            
            # Should have 2 handlers (console + file)
            assert len(root_logger.handlers) >= 2

    def test_setup_logging_with_log_dir_creates_directory(self):
        """Test setup_logging creates parent directory for log file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_log_dir = os.path.join(temp_dir, "nested", "directory")
            
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            setup_logging(log_level="INFO", log_dir=new_log_dir, component="test")
            
            # Check nested directories were created
            assert os.path.exists(new_log_dir)
            
            # Check log file exists
            log_file = Path(new_log_dir) / "test.log"
            assert log_file.exists()


class TestGetLogger:
    """Tests for get_logger function"""

    def test_get_logger_returns_logger(self):
        """Test get_logger returns a logger instance"""
        logger = get_logger("test_module")
        
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_names(self):
        """Test get_logger returns different loggers for different names"""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        
        assert logger1.name != logger2.name
        assert isinstance(logger1, logging.Logger)
        assert isinstance(logger2, logging.Logger)
