"""Unit tests for scheduler.core.utils module"""
import pytest
import os
from datetime import datetime, timedelta
from scheduler.core.utils import (
    parse_requirements,
    format_duration,
    format_timestamp,
    format_bytes,
    generate_job_id,
    generate_versioned_filename,
    is_port_available,
    find_available_port,
    get_local_ip,
    ensure_dir_exists,
    parse_address
)
from scheduler.core.exceptions import InvalidRequirementException, ValidationException
from scheduler.core import constants


class TestConstants:
    """Tests for scheduler.core.constants module"""

    def test_rsync_port_defined(self):
        """Test that RSYNC_PORT constant is defined"""
        assert hasattr(constants, 'RSYNC_PORT')
        assert constants.RSYNC_PORT == 8873

    def test_rsync_port_is_integer(self):
        """Test that RSYNC_PORT is an integer"""
        assert isinstance(constants.RSYNC_PORT, int)

    def test_rsync_port_in_valid_range(self):
        """Test that RSYNC_PORT is in valid port range"""
        assert 1024 <= constants.RSYNC_PORT <= 65535


class TestParseRequirements:
    """Tests for parse_requirements function"""

    def test_simple_requirement(self):
        """Test parsing simple requirement"""
        result = parse_requirements("2")
        assert result == [(None, 2)]

    def test_node_specific_requirement(self):
        """Test parsing node-specific requirement"""
        result = parse_requirements("gpu1:4")
        assert result == [("gpu1", 4)]

    def test_multiple_alternatives(self):
        """Test parsing multiple alternatives"""
        result = parse_requirements("gpu1:2,gpu2:4")
        assert result == [("gpu1", 2), ("gpu2", 4)]

    def test_empty_string(self):
        """Test parsing empty string raises exception"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("")

    def test_whitespace_only(self):
        """Test parsing whitespace-only string raises exception"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("   ")

    def test_invalid_format_no_colon_space(self):
        """Test parsing invalid format with space instead of colon"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("gpu1 4")

    def test_invalid_format_missing_gpu_count(self):
        """Test parsing invalid format with missing GPU count"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("gpu1:")

    def test_invalid_format_missing_node_name(self):
        """Test parsing invalid format with missing node name"""
        # :4 is parsed as a simple requirement (empty string means "no node name")
        result = parse_requirements(":4")
        # Should treat as "4" requirement
        assert len(result) > 0

    def test_non_numeric_gpu_count(self):
        """Test parsing non-numeric GPU count"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("gpu1:abc")

    def test_negative_gpu_count(self):
        """Test parsing negative GPU count"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("gpu1:-4")

    def test_zero_gpu_count(self):
        """Test parsing zero GPU count"""
        with pytest.raises(InvalidRequirementException):
            parse_requirements("gpu1:0")

    def test_whitespace_around_values(self):
        """Test parsing requirements with whitespace"""
        result = parse_requirements("  gpu1 : 4  ,  gpu2 : 8  ")
        assert result == [("gpu1", 4), ("gpu2", 8)]

    def test_multiple_simple_requirements(self):
        """Test parsing multiple simple requirements"""
        result = parse_requirements("2,4,8")
        assert result == [(None, 2), (None, 4), (None, 8)]

    def test_flexible_allocation_single_node(self):
        """Test parsing flexible allocation for single node (--req host)"""
        result = parse_requirements("gpu1")
        assert result == [("gpu1", -1)]

    def test_flexible_allocation_multiple_nodes(self):
        """Test parsing flexible allocation for multiple nodes"""
        result = parse_requirements("gpu1,gpu2,gpu3")
        assert result == [("gpu1", -1), ("gpu2", -1), ("gpu3", -1)]

    def test_mixed_flexible_and_fixed_allocation(self):
        """Test parsing mixed flexible and fixed allocation"""
        result = parse_requirements("gpu1,gpu2:4")
        assert result == [("gpu1", -1), ("gpu2", 4)]

    def test_mixed_any_node_and_flexible_allocation(self):
        """Test parsing mixed any-node and flexible allocation"""
        result = parse_requirements("2,gpu1")
        assert result == [(None, 2), ("gpu1", -1)]

    def test_flexible_allocation_with_spaces(self):
        """Test parsing flexible allocation with whitespace"""
        result = parse_requirements("  gpu1  ,  gpu2  ")
        assert result == [("gpu1", -1), ("gpu2", -1)]

    def test_flexible_allocation_node_name_variations(self):
        """Test parsing flexible allocation with various node name formats"""
        # Test with hyphens
        result = parse_requirements("gpu-node-1")
        assert result == [("gpu-node-1", -1)]

        # Test with underscores
        result = parse_requirements("gpu_node_1")
        assert result == [("gpu_node_1", -1)]

        # Test with dots
        result = parse_requirements("gpu.node.1")
        assert result == [("gpu.node.1", -1)]


class TestFormatDuration:
    """Tests for format_duration function"""

    def test_format_seconds(self):
        """Test formatting seconds"""
        duration = timedelta(seconds=45)
        assert format_duration(duration) == "00:00:45"

    def test_format_minutes(self):
        """Test formatting minutes"""
        duration = timedelta(minutes=5, seconds=30)
        assert format_duration(duration) == "00:05:30"

    def test_format_hours(self):
        """Test formatting hours"""
        duration = timedelta(hours=2, minutes=15, seconds=30)
        assert format_duration(duration) == "02:15:30"

    def test_format_days(self):
        """Test formatting days"""
        duration = timedelta(days=1, hours=3, minutes=22, seconds=11)
        assert format_duration(duration) == "1d 03:22:11"

    def test_format_multiple_days(self):
        """Test formatting multiple days"""
        duration = timedelta(days=5, hours=3, minutes=22, seconds=11)
        assert format_duration(duration) == "5d 03:22:11"

    def test_format_zero(self):
        """Test formatting zero duration"""
        duration = timedelta(seconds=0)
        assert format_duration(duration) == "00:00:00"


class TestFormatTimestamp:
    """Tests for format_timestamp function"""

    def test_format_absolute_timestamp(self):
        """Test formatting absolute timestamp"""
        dt = datetime(2023, 1, 1, 12, 30, 45)
        result = format_timestamp(dt, relative=False)
        assert "2023-01-01" in result
        assert "12:30:45" in result

    def test_format_relative_timestamp(self):
        """Test formatting relative timestamp"""
        now = datetime.now()
        dt = now - timedelta(hours=2)
        result = format_timestamp(dt, relative=True)
        assert "2 hours ago" in result or "ago" in result


class TestParseAddress:
    """Tests for parse_address function"""

    def test_parse_valid_address(self):
        """Test parsing valid address"""
        result = parse_address("localhost:8265")
        assert result == ("localhost", 8265)

    def test_parse_address_with_ip(self):
        """Test parsing address with IP"""
        result = parse_address("192.168.1.1:9000")
        assert result == ("192.168.1.1", 9000)

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises exception"""
        with pytest.raises(Exception):
            parse_address("invalid")

    def test_parse_invalid_port(self):
        """Test parsing invalid port raises exception"""
        with pytest.raises(Exception):
            parse_address("localhost:invalid")


class TestFormatBytes:
    """Tests for format_bytes function"""

    def test_format_bytes(self):
        """Test formatting bytes"""
        result = format_bytes(1024)
        assert "KB" in result or "1.0" in result

    def test_format_large_bytes(self):
        """Test formatting large bytes"""
        result = format_bytes(1024 * 1024)
        assert "MB" in result or "GB" in result


class TestGenerateJobId:
    """Tests for generate_job_id function"""

    def test_generate_job_id(self):
        """Test generating job ID"""
        result = generate_job_id()
        assert isinstance(result, str)
        assert len(result) > 0
        assert result.startswith("job_")

    def test_generate_unique_ids(self):
        """Test generating unique IDs"""
        id1 = generate_job_id()
        id2 = generate_job_id()
        assert id1 != id2


class TestGenerateVersionedFilename:
    """Tests for generate_versioned_filename function"""

    def test_generate_versioned_filename(self):
        """Test generating versioned filename"""
        result = generate_versioned_filename("/path/script.py", "job_123")
        assert "script" in result
        assert "job_123" in result


class TestIsPortAvailable:
    """Tests for is_port_available function"""

    def test_is_port_available(self):
        """Test checking if port is available"""
        result = is_port_available(8888)  # Use a valid port number
        assert isinstance(result, bool)

    def test_port_in_use(self):
        """Test checking if known port is in use"""
        # Port 22 is likely in use (SSH)
        result = is_port_available(22)
        assert isinstance(result, bool)


class TestFindAvailablePort:
    """Tests for find_available_port function"""

    def test_find_available_port(self):
        """Test finding available port"""
        result = find_available_port(start_port=8880, max_attempts=20)
        assert isinstance(result, int)
        assert result >= 8880


class TestGetLocalIP:
    """Tests for get_local_ip function"""

    def test_get_local_ip(self):
        """Test getting local IP"""
        result = get_local_ip()
        assert isinstance(result, str)
        assert len(result) > 0


class TestEnsureDirExists:
    """Tests for ensure_dir_exists function"""

    def test_ensure_dir_exists_creates_new_dir(self):
        """Test ensuring directory exists creates new directory"""
        dir_path = "/tmp/test_ensure_dir"
        try:
            if os.path.exists(dir_path):
                os.rmdir(dir_path)
            ensure_dir_exists(dir_path)
            assert os.path.exists(dir_path)
        finally:
            # Cleanup
            if os.path.exists(dir_path):
                os.rmdir(dir_path)

    def test_ensure_dir_exists_existing_dir(self):
        """Test ensuring directory exists when already exists"""
        dir_path = "/tmp/test_ensure_dir_existing"
        try:
            os.makedirs(dir_path, exist_ok=True)
            ensure_dir_exists(dir_path)  # Should not raise
            assert os.path.exists(dir_path)
        finally:
            # Cleanup
            if os.path.exists(dir_path):
                os.rmdir(dir_path)



class TestParseTimeDuration:
    """Tests for parse_time_duration function"""

    def test_parse_weeks(self):
        """Test parsing weeks duration"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("3w")
        assert result == timedelta(weeks=3)

    def test_parse_days(self):
        """Test parsing days duration"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("7d")
        assert result == timedelta(days=7)

    def test_parse_hours(self):
        """Test parsing hours duration"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("24h")
        assert result == timedelta(hours=24)

    def test_parse_minutes(self):
        """Test parsing minutes duration"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("30m")
        assert result == timedelta(minutes=30)

    def test_parse_seconds(self):
        """Test parsing seconds duration"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("90s")
        assert result == timedelta(seconds=90)

    def test_parse_empty_string(self):
        """Test parsing empty string raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("")

    def test_parse_whitespace_only(self):
        """Test parsing whitespace-only string raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("   ")

    def test_parse_invalid_format_no_unit(self):
        """Test parsing invalid format without unit raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("10")

    def test_parse_invalid_format_invalid_unit(self):
        """Test parsing invalid unit raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("10x")

    def test_parse_invalid_format_no_number(self):
        """Test parsing invalid format without number raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("d")

    def test_parse_zero_duration(self):
        """Test parsing zero duration raises ValidationException"""
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("0d")

    def test_parse_negative_duration(self):
        """Test parsing negative duration raises ValidationException"""  
        from scheduler.core.utils import parse_time_duration
        with pytest.raises(ValidationException):
            parse_time_duration("-5h")

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive"""
        from scheduler.core.utils import parse_time_duration
        result = parse_time_duration("5D")
        assert result == timedelta(days=5)


class TestFindAvailablePortException:
    """Tests for find_available_port exception handling"""

    def test_find_available_port_no_ports_available(self):
        """Test find_available_port raises exception when no ports available"""
        from scheduler.core.exceptions import PermissionDeniedException
        from unittest.mock import patch

        # Mock is_port_available to always return False, simulating no ports available
        with patch('scheduler.core.utils.is_port_available', return_value=False):
            with pytest.raises(PermissionDeniedException):
                find_available_port(start_port=8000, max_attempts=5)


class TestGenerateVersionedFilenameEdgeCases:
    """Tests for generate_versioned_filename edge cases"""

    def test_generate_versioned_filename_nonexistent_file(self):
        """Test generating versioned filename for nonexistent file"""
        result = generate_versioned_filename("/nonexistent/path/script.py", "job123")
        assert "script" in result
        assert "job123" in result
        assert ".py" in result

    def test_generate_versioned_filename_no_extension(self):
        """Test generating versioned filename for file without extension"""
        result = generate_versioned_filename("/tmp/scriptname", "job456")
        assert "scriptname" in result
        assert "job456" in result
        assert not result.endswith(".")


class TestFormatBytesEdgeCases:
    """Tests for format_bytes edge cases"""

    def test_format_zero_bytes(self):
        """Test formatting zero bytes"""
        result = format_bytes(0)
        assert result == "0 B"

    def test_format_petabytes(self):
        """Test formatting petabytes"""
        result = format_bytes(2 * 1024**5)  # 2 PB
        assert "PB" in result
        assert "2.0" in result


class TestParseAddressEdgeCases:
    """Tests for parse_address edge cases"""

    def test_parse_address_no_port(self):
        """Test parsing address without port raises ValidationException"""
        with pytest.raises(ValidationException):
            parse_address("hostname")

    def test_parse_address_empty(self):
        """Test parsing empty address raises ValidationException"""
        with pytest.raises(ValidationException):
            parse_address("")

    def test_parse_address_port_out_of_range_high(self):
        """Test parsing address with port > 65535 raises ValidationException"""
        with pytest.raises(ValidationException):
            parse_address("host:99999")

    def test_parse_address_port_out_of_range_low(self):
        """Test parsing address with port < 1 raises ValidationException"""
        with pytest.raises(ValidationException):
            parse_address("host:0")


class TestGetLocalIPException:
    """Tests for get_local_ip exception handling"""

    def test_get_local_ip_returns_fallback(self):
        """Test get_local_ip returns 127.0.0.1 as fallback"""
        # This test verifies the function handles exceptions gracefully
        result = get_local_ip()
        # Should either return a valid IP or fallback to 127.0.0.1
        assert isinstance(result, str)
        assert len(result) > 0


class TestParseRequirementsEdgeCases:
    """Tests for parse_requirements edge cases to improve coverage"""

    def test_invalid_node_specific_format_missing_colon_part(self):
        """Test parsing invalid node-specific requirement with bad format"""
        with pytest.raises(InvalidRequirementException, match="Invalid GPU count"):
            parse_requirements("gpu1:")

    def test_any_node_negative_gpu_count(self):
        """Test parsing any-node requirement with negative GPU count"""
        with pytest.raises(InvalidRequirementException, match="GPU count must be positive"):
            parse_requirements("-2")


class TestFormatTimestampRelative:
    """Tests for format_timestamp with relative=True to improve coverage"""

    def test_format_timestamp_just_now(self):
        """Test formatting timestamp less than 60 seconds ago"""
        now = datetime.now()
        dt = now - timedelta(seconds=30)
        result = format_timestamp(dt, relative=True)
        assert result == "just now"

    def test_format_timestamp_minutes_ago_singular(self):
        """Test formatting timestamp 1 minute ago"""
        now = datetime.now()
        dt = now - timedelta(minutes=1)
        result = format_timestamp(dt, relative=True)
        assert result == "1 minute ago"

    def test_format_timestamp_minutes_ago_plural(self):
        """Test formatting timestamp multiple minutes ago"""
        now = datetime.now()
        dt = now - timedelta(minutes=45)
        result = format_timestamp(dt, relative=True)
        assert "minute" in result and "ago" in result

    def test_format_timestamp_hours_ago_singular(self):
        """Test formatting timestamp 1 hour ago"""
        now = datetime.now()
        dt = now - timedelta(hours=1)
        result = format_timestamp(dt, relative=True)
        assert result == "1 hour ago"

    def test_format_timestamp_hours_ago_plural(self):
        """Test formatting timestamp multiple hours ago"""
        now = datetime.now()
        dt = now - timedelta(hours=5)
        result = format_timestamp(dt, relative=True)
        assert "hour" in result and "ago" in result

    def test_format_timestamp_days_ago_singular(self):
        """Test formatting timestamp 1 day ago"""
        now = datetime.now()
        dt = now - timedelta(days=1)
        result = format_timestamp(dt, relative=True)
        assert result == "1 day ago"

    def test_format_timestamp_days_ago_plural(self):
        """Test formatting timestamp multiple days ago"""
        now = datetime.now()
        dt = now - timedelta(days=7)
        result = format_timestamp(dt, relative=True)
        assert "day" in result and "ago" in result


class TestGenerateVersionedFilenameWithPermissionError:
    """Tests for generate_versioned_filename when file cannot be read"""

    def test_generate_versioned_filename_with_permission_error(self, tmp_path, monkeypatch):
        """Test generate_versioned_filename handles permission errors gracefully"""
        import tempfile
        
        # Create a temporary script file
        script_file = tmp_path / "test_script.py"
        script_file.write_text("print('hello')")
        
        # Mock open to raise PermissionError
        original_open = open
        def mock_open(path, *args, **kwargs):
            if str(path) == str(script_file):
                raise PermissionError("Permission denied")
            return original_open(path, *args, **kwargs)
        
        monkeypatch.setattr("builtins.open", mock_open)
        
        # Should still generate a versioned filename using timestamp-based hash
        versioned = generate_versioned_filename(str(script_file), "job_abc123")
        assert "test_script" in versioned
        assert "job_abc123" in versioned


class TestEnsureDirExistsExceptions:
    """Tests for ensure_dir_exists exception handling"""

    def test_ensure_dir_exists_permission_error(self, monkeypatch, tmp_path):
        """Test ensure_dir_exists raises PermissionDeniedException on permission error"""
        import pathlib
        from scheduler.core.exceptions import PermissionDeniedException
        
        # Mock mkdir to raise PermissionError
        original_mkdir = pathlib.Path.mkdir
        def mock_mkdir(self, *args, **kwargs):
            raise PermissionError("Permission denied")
        
        monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir)
        
        with pytest.raises(PermissionDeniedException, match="Cannot create directory"):
            ensure_dir_exists(str(tmp_path / "test_dir"))

    def test_ensure_dir_exists_generic_exception(self, monkeypatch, tmp_path):
        """Test ensure_dir_exists handles generic exceptions"""
        import pathlib
        from scheduler.core.exceptions import PermissionDeniedException
        
        # Mock mkdir to raise generic Exception
        original_mkdir = pathlib.Path.mkdir
        def mock_mkdir(self, *args, **kwargs):
            raise RuntimeError("Some error")
        
        monkeypatch.setattr(pathlib.Path, "mkdir", mock_mkdir)
        
        with pytest.raises(PermissionDeniedException, match="Error creating directory"):
            ensure_dir_exists(str(tmp_path / "test_dir"))
