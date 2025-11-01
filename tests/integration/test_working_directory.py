"""Integration tests for working directory handling"""
import os
import tempfile
import shutil
import pytest
from unittest.mock import create_autospec
from scheduler.head.job_manager import JobManager
from scheduler.head.persistence import PersistenceManager
from scheduler.core.config import Config
from scheduler.core.models import JobStatus


@pytest.fixture
def mock_config():
    """Create a mock config object"""
    config = create_autospec(Config, instance=True, spec_set=True)
    return config


@pytest.fixture
def mock_persistence():
    """Create a mock persistence manager"""
    persistence = create_autospec(PersistenceManager, instance=True, spec_set=True)
    persistence.load_all_jobs.return_value = []
    persistence.save_job.return_value = None
    return persistence


@pytest.fixture
def job_manager(mock_config, mock_persistence):
    """Create a test job manager"""
    return JobManager(mock_persistence, mock_config)


class TestWorkingDirectory:
    """Test working directory handling"""
    
    def test_working_dir_is_set_from_submission(self, job_manager):
        """Test that working directory is preserved from submission"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a test script
            script_path = os.path.join(temp_dir, 'test.sh')
            with open(script_path, 'w') as f:
                f.write('#!/bin/bash\npwd\n')
            
            # Submit job with explicit working directory
            job = job_manager.submit_job(
                script=script_path,
                requirements="1",
                working_dir=temp_dir
            )
            
            # Verify working directory is set correctly
            assert job.working_dir == temp_dir
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_working_dir_uses_cwd_if_not_specified(self, job_manager):
        """Test that working directory defaults to cwd on head node if not specified"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a test script
            script_path = os.path.join(temp_dir, 'test.sh')
            with open(script_path, 'w') as f:
                f.write('#!/bin/bash\npwd\n')
            
            # Change to temp directory
            original_cwd = os.getcwd()
            try:
                os.chdir(temp_dir)
                
                # Submit job without working directory
                job = job_manager.submit_job(
                    script=script_path,
                    requirements="1",
                    working_dir=None
                )
                
                # Should use current working directory (temp_dir)
                assert job.working_dir == temp_dir
            finally:
                os.chdir(original_cwd)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_snapshot_uses_working_dir(self, job_manager):
        """Test that snapshot is created using the correct working directory"""
        temp_dir = tempfile.mkdtemp()
        try:
            # Create a test script
            script_path = os.path.join(temp_dir, 'test.py')
            with open(script_path, 'w') as f:
                f.write('print("test")\n')
            
            # Submit job with explicit working directory
            job = job_manager.submit_job(
                script=script_path,
                requirements="1",
                working_dir=temp_dir
            )
            
            # Verify snapshot was created with correct working directory
            assert job.snapshot_working_dir == temp_dir
            assert job.snapshot_ref is not None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
