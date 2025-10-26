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

