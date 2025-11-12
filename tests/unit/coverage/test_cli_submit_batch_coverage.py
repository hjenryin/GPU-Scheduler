"""
Comprehensive tests for cli/submit_batch.py to improve coverage to 90%+
"""
import os
import pytest
import tempfile
from unittest.mock import MagicMock, patch, mock_open, create_autospec

from scheduler.cli.submit_batch import submit_batch_command
from scheduler.core import ValidationException, ConnectionException
from scheduler.api.client import SchedulerClient
from scheduler.core.models import Job


@patch('scheduler.cli.submit_batch.os.path.exists', autospec=True)
def test_submit_batch_file_not_found(mock_exists):
    """Test submit_batch_command when script list file doesn't exist"""
    mock_exists.return_value = False
    
    result = submit_batch_command("/nonexistent/file.txt")
    assert result == 4


@patch('scheduler.cli.submit_batch.os.path.exists', autospec=True)
@patch('builtins.open', side_effect=IOError("Cannot read file"))  # Cannot use autospec with side_effect
def test_submit_batch_cannot_read_file(mock_file, mock_exists):
    """Test submit_batch_command when file cannot be read"""
    mock_exists.return_value = True
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 1


@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='')
def test_submit_batch_empty_file(mock_file, mock_exists):
    """Test submit_batch_command with empty file"""
    mock_exists.return_value = True
    
    result = submit_batch_command("/tmp/empty.txt")
    assert result == 1


@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='# Comment only\n  \n')
def test_submit_batch_only_comments(mock_file, mock_exists):
    """Test submit_batch_command with only comments and whitespace"""
    mock_exists.return_value = True
    
    result = submit_batch_command("/tmp/comments.txt")
    assert result == 1


def test_submit_batch_invalid_env_var_format():
    """Test submit_batch_command with invalid environment variable format"""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("script1.py\n")
        f.flush()
        filename = f.name
    
    try:
        result = submit_batch_command(filename, env=["INVALIDFORMAT"])
        assert result == 2
    finally:
        os.unlink(filename)


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_success(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command successful batch submission"""
    mock_exists.return_value = True

    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []

    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = []

    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", req="2")
    assert result == 0
    assert mock_client.submit_job.call_count == 2


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py arg1 arg2\nscript2.py\n')
def test_submit_batch_with_script_args(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command with script arguments"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 0
    
    # Verify first job was submitted with args
    first_call = mock_client.submit_job.call_args_list[0]
    assert first_call[1]['script_args'] == ['arg1', 'arg2']


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_with_env_vars(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command with environment variables"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", env=["KEY1=value1", "KEY2=value2"])
    assert result == 0
    
    # Verify env_vars were passed
    first_call = mock_client.submit_job.call_args_list[0]
    assert first_call[1]['env_vars'] == {"KEY1": "value1", "KEY2": "value2"}


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\nscript3.py\n')
def test_submit_batch_sequential_mode(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command in sequential mode"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = ["job1"]
    
    mock_job3 = create_autospec(Job, instance=True, spec_set=True)
    mock_job3.job_id = "job3"
    mock_job3.status.value = "pending"
    mock_job3.dependencies = ["job2"]
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2, mock_job3]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", sequential=True)
    assert result == 0
    
    # Verify dependencies were set correctly
    second_call = mock_client.submit_job.call_args_list[1]
    assert "job1" in second_call[1]['dependencies']
    
    third_call = mock_client.submit_job.call_args_list[2]
    assert "job2" in third_call[1]['dependencies']


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_with_initial_dependencies(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command with initial dependencies"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = ["dep1", "dep2"]
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = ["dep1", "dep2"]
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", depends_on=["dep1", "dep2"])
    assert result == 0
    
    # Verify dependencies were passed
    first_call = mock_client.submit_job.call_args_list[0]
    assert "dep1" in first_call[1]['dependencies']
    assert "dep2" in first_call[1]['dependencies']


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_validation_error(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command when job submission fails with ValidationException"""
    mock_exists.return_value = True
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = ValidationException("Invalid job")
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 1


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\nscript3.py\n')
def test_submit_batch_sequential_stops_on_error(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command stops in sequential mode after error"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [
        mock_job1,
        ValidationException("Invalid job"),
        MagicMock()  # Should not reach this
    ]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", sequential=True)
    assert result == 1
    assert mock_client.submit_job.call_count == 2  # Should stop after second job fails


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\nscript3.py\n')
def test_submit_batch_connection_error(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command when ConnectionException occurs"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [
        mock_job1,
        ConnectionException("Connection lost")
    ]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 1


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_generic_exception(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command when generic exception occurs"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [
        mock_job1,
        RuntimeError("Unexpected error")
    ]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 1


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
def test_submit_batch_validation_exception_on_connect(mock_load_config):
    """Test submit_batch_command when ValidationException on connection"""
    mock_load_config.side_effect = ValidationException("Invalid config")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("script1.py\n")
        f.flush()
        filename = f.name
    
    try:
        result = submit_batch_command(filename)
        assert result == 2
    finally:
        os.unlink(filename)


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
def test_submit_batch_connection_exception_on_connect(mock_load_config):
    """Test submit_batch_command when ConnectionException on connection"""
    mock_load_config.side_effect = ConnectionException("Cannot connect")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("script1.py\n")
        f.flush()
        filename = f.name
    
    try:
        result = submit_batch_command(filename)
        assert result == 3
    finally:
        os.unlink(filename)


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
def test_submit_batch_generic_exception_on_connect(mock_load_config):
    """Test submit_batch_command when generic exception on connection"""
    mock_load_config.side_effect = RuntimeError("Unexpected error")
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("script1.py\n")
        f.flush()
        filename = f.name
    
    try:
        result = submit_batch_command(filename)
        assert result == 1
    finally:
        os.unlink(filename)


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_with_resolved_dependencies(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command displays resolved dependencies"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    # Simulate server resolving "latest" to actual job ID
    mock_job1.dependencies = ["actual-job-123", "dep2"]
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = ["actual-job-456", "dep2"]
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", depends_on=["latest", "dep2"])
    assert result == 0


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='/path/to/script1.py\nbare_command\n')
@patch('scheduler.cli.submit_batch.os.path.dirname')
@patch('scheduler.cli.submit_batch.os.path.abspath')
def test_submit_batch_path_resolution(mock_abspath, mock_dirname, mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command handles path resolution correctly"""
    mock_exists.return_value = True
    mock_dirname.side_effect = lambda x: "/path/to" if x == "/path/to/script1.py" else ""
    mock_abspath.return_value = "/absolute/path/to/script1.py"
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt")
    assert result == 0


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\nscript3.py\n')
def test_submit_batch_sequential_with_connection_error(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command stops in sequential mode on ConnectionException"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [
        mock_job1,
        ConnectionException("Connection lost")
    ]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", sequential=True)
    assert result == 1
    assert mock_client.submit_job.call_count == 2


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\nscript3.py\n')
def test_submit_batch_sequential_with_generic_error(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command stops in sequential mode on generic exception"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [
        mock_job1,
        RuntimeError("Unexpected error")
    ]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", sequential=True)
    assert result == 1
    assert mock_client.submit_job.call_count == 2


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\nscript2.py\n')
def test_submit_batch_with_working_dir(mock_file, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command with specified working directory"""
    mock_exists.return_value = True
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_job2 = create_autospec(Job, instance=True, spec_set=True)
    mock_job2.job_id = "job2"
    mock_job2.status.value = "pending"
    mock_job2.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.side_effect = [mock_job1, mock_job2]
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", working_dir="/custom/dir")
    assert result == 0
    
    # Verify working_dir was passed
    first_call = mock_client.submit_job.call_args_list[0]
    assert first_call[1]['working_dir'] == "/custom/dir"


@patch('scheduler.cli.submit_batch.load_config', autospec=True)
@patch('scheduler.cli.submit_batch.SchedulerClient')
@patch('scheduler.cli.submit_batch.os.path.exists')
@patch('scheduler.cli.submit_batch.os.getcwd')
@patch('builtins.open', new_callable=mock_open, read_data='script1.py\n')
def test_submit_batch_default_working_dir(mock_file, mock_getcwd, mock_exists, mock_client_class, mock_load_config):
    """Test submit_batch_command uses current directory as default working_dir"""
    mock_exists.return_value = True
    mock_getcwd.return_value = "/current/dir"
    
    mock_job1 = create_autospec(Job, instance=True, spec_set=True)
    mock_job1.job_id = "job1"
    mock_job1.status.value = "pending"
    mock_job1.dependencies = []
    
    mock_client = create_autospec(SchedulerClient, instance=True, spec_set=True)
    mock_client.submit_job.return_value = mock_job1
    mock_client_class.return_value = mock_client
    
    result = submit_batch_command("/tmp/scripts.txt", working_dir=None)
    assert result == 0
    
    # Verify working_dir defaults to current directory
    first_call = mock_client.submit_job.call_args_list[0]
    assert first_call[1]['working_dir'] == "/current/dir"
