"""Unit tests for TUI utility functions."""

from datetime import timedelta, datetime
from unittest.mock import patch

from scheduler.tui.utils import (
    format_gpu_memory,
    get_status_color,
    format_runtime,
    format_time_ago,
    create_gpu_utilization_bar,
    wrap_in_api_client
)


class TestFormatGPUMemory:
    """Test GPU memory formatting function."""

    def test_format_gpu_memory_bytes(self):
        """Test formatting small memory values in bytes."""
        assert format_gpu_memory(0) == "0.0G"
        assert format_gpu_memory(1024) == "0.0G"  # 1KB
        assert format_gpu_memory(1024 * 1024) == "0.0G"  # 1MB

    def test_format_gpu_memory_gigabytes(self):
        """Test formatting memory values in gigabytes."""
        assert format_gpu_memory(1024 ** 3) == "1.0G"  # 1GB
        assert format_gpu_memory(2 * 1024 ** 3) == "2.0G"  # 2GB
        assert format_gpu_memory(8 * 1024 ** 3) == "8.0G"  # 8GB

    def test_format_gpu_memory_fractional(self):
        """Test formatting fractional gigabyte values."""
        # 1.5GB
        assert format_gpu_memory(int(1.5 * 1024 ** 3)) == "1.5G"
        # 12.3GB
        assert format_gpu_memory(int(12.3 * 1024 ** 3)) == "12.3G"
        # 0.5GB
        assert format_gpu_memory(int(0.5 * 1024 ** 3)) == "0.5G"

    def test_format_gpu_memory_large_values(self):
        """Test formatting large memory values."""
        # 24GB (typical high-end GPU)
        assert format_gpu_memory(24 * 1024 ** 3) == "24.0G"
        # 80GB (A100)
        assert format_gpu_memory(80 * 1024 ** 3) == "80.0G"


class TestGetStatusColor:
    """Test status color mapping function."""

    def test_job_status_colors(self):
        """Test job status color mapping."""
        assert get_status_color("pending") == "yellow"
        assert get_status_color("running") == "green"
        assert get_status_color("completed") == "blue"
        assert get_status_color("failed") == "red"
        assert get_status_color("cancelled") == "gray"

    def test_node_status_colors(self):
        """Test node status color mapping."""
        assert get_status_color("connected") == "green"
        assert get_status_color("disconnected") == "red"

    def test_case_insensitive(self):
        """Test that status colors are case insensitive."""
        assert get_status_color("PENDING") == "yellow"
        assert get_status_color("Running") == "green"
        assert get_status_color("FAILED") == "red"

    def test_unknown_status(self):
        """Test unknown status returns default color."""
        assert get_status_color("unknown") == "white"
        assert get_status_color("") == "white"
        assert get_status_color("invalid_status") == "white"


class TestFormatRuntime:
    """Test runtime formatting function."""

    def test_format_runtime_none(self):
        """Test formatting None runtime."""
        assert format_runtime(None) == "-"

    def test_format_runtime_seconds(self):
        """Test formatting runtime in seconds."""
        runtime = timedelta(seconds=30)
        assert format_runtime(runtime) == "00:00:30"

    def test_format_runtime_minutes(self):
        """Test formatting runtime in minutes."""
        runtime = timedelta(minutes=5, seconds=30)
        assert format_runtime(runtime) == "00:05:30"

    def test_format_runtime_hours(self):
        """Test formatting runtime in hours."""
        runtime = timedelta(hours=2, minutes=15, seconds=45)
        assert format_runtime(runtime) == "02:15:45"

    def test_format_runtime_long_duration(self):
        """Test formatting long runtime durations."""
        runtime = timedelta(hours=25, minutes=30, seconds=15)
        assert format_runtime(runtime) == "25:30:15"

    def test_format_runtime_zero(self):
        """Test formatting zero runtime."""
        runtime = timedelta(seconds=0)
        assert format_runtime(runtime) == "00:00:00"

    def test_format_runtime_fractional_seconds(self):
        """Test formatting runtime with fractional seconds (should truncate)."""
        runtime = timedelta(seconds=30.7)
        assert format_runtime(runtime) == "00:00:30"


class TestFormatTimeAgo:
    """Test time ago formatting function."""

    def test_format_time_ago_none(self):
        """Test formatting None timestamp."""
        assert format_time_ago(None) == "-"

    def test_format_time_ago_seconds(self):
        """Test formatting timestamp from seconds ago."""
        now = datetime.now()
        timestamp = now - timedelta(seconds=30)
        result = format_time_ago(timestamp)
        assert result == "30s ago" or result == "29s ago"  # Allow 1s variance

    def test_format_time_ago_minutes(self):
        """Test formatting timestamp from minutes ago."""
        now = datetime.now()
        timestamp = now - timedelta(minutes=5, seconds=30)
        assert format_time_ago(timestamp) == "5m ago"

    def test_format_time_ago_hours(self):
        """Test formatting timestamp from hours ago."""
        now = datetime.now()
        timestamp = now - timedelta(hours=2, minutes=30)
        assert format_time_ago(timestamp) == "2h ago"

    def test_format_time_ago_days(self):
        """Test formatting timestamp from days ago."""
        now = datetime.now()
        timestamp = now - timedelta(days=3, hours=12)
        assert format_time_ago(timestamp) == "3d ago"

    def test_format_time_ago_just_now(self):
        """Test formatting timestamp from the future (should show just now)."""
        now = datetime.now()
        timestamp = now + timedelta(seconds=5)
        assert format_time_ago(timestamp) == "just now"

    def test_format_time_ago_boundary_60_seconds(self):
        """Test formatting timestamp at 60 seconds boundary."""
        now = datetime.now()
        timestamp = now - timedelta(seconds=60)
        assert format_time_ago(timestamp) == "1m ago"

    def test_format_time_ago_boundary_3600_seconds(self):
        """Test formatting timestamp at 1 hour boundary."""
        now = datetime.now()
        timestamp = now - timedelta(seconds=3600)
        assert format_time_ago(timestamp) == "1h ago"


class TestCreateGPUUtilizationBar:
    """Test GPU utilization bar creation function."""

    def test_create_gpu_utilization_bar_zero(self):
        """Test creating bar for 0% utilization."""
        bar = create_gpu_utilization_bar(0.0, width=10)
        assert bar == "░░░░░░░░░░   0%"
        assert len(bar) == 15  # 10 chars + "   0%"

    def test_create_gpu_utilization_bar_full(self):
        """Test creating bar for 100% utilization."""
        bar = create_gpu_utilization_bar(100.0, width=10)
        assert bar == "██████████ 100%"
        assert len(bar) == 15  # 10 chars + " 100%"

    def test_create_gpu_utilization_bar_half(self):
        """Test creating bar for 50% utilization."""
        bar = create_gpu_utilization_bar(50.0, width=10)
        assert bar == "█████░░░░░  50%"
        assert len(bar) == 15  # 10 chars + "  50%"

    def test_create_gpu_utilization_bar_partial(self):
        """Test creating bar for partial utilization."""
        bar = create_gpu_utilization_bar(25.0, width=10)
        assert bar == "██░░░░░░░░  25%"
        assert len(bar) == 15

    def test_create_gpu_utilization_bar_custom_width(self):
        """Test creating bar with custom width."""
        bar = create_gpu_utilization_bar(60.0, width=5)
        assert bar == "███░░  60%"
        assert len(bar) == 10  # 5 chars + "  60%"

    def test_create_gpu_utilization_bar_default_width(self):
        """Test creating bar with default width."""
        bar = create_gpu_utilization_bar(40.0)
        assert len(bar) == 25  # 20 chars + "  40%"
        assert "40%" in bar

    def test_create_gpu_utilization_bar_edge_cases(self):
        """Test edge cases for utilization bar."""
        # Very small utilization
        bar = create_gpu_utilization_bar(1.0, width=10)
        assert "1%" in bar
        assert bar.count("█") == 0  # Should be all empty

        # Very high utilization
        bar = create_gpu_utilization_bar(99.0, width=10)
        assert "99%" in bar
        assert bar.count("█") == 9  # Should be mostly filled

    def test_create_gpu_utilization_bar_rounding(self):
        """Test that utilization values are properly rounded."""
        # 33.3% should round to 33%
        bar = create_gpu_utilization_bar(33.3, width=10)
        assert "33%" in bar

        # 66.7% should round to 67%
        bar = create_gpu_utilization_bar(66.7, width=10)
        assert "67%" in bar


class TestWrapInAPIClient:
    """Test API client wrapper decorator."""

    def test_wrap_in_api_client_success(self):
        """Test wrapper with successful function execution."""
        @wrap_in_api_client
        def test_func():
            return "success"

        result = test_func()
        assert result == "success"

    def test_wrap_in_api_client_exception(self):
        """Test wrapper with exception handling."""
        @wrap_in_api_client
        def test_func():
            raise ValueError("Test error")

        result = test_func()
        assert result is None

    def test_wrap_in_api_client_with_args(self):
        """Test wrapper with function arguments."""
        @wrap_in_api_client
        def test_func(arg1, arg2, kwarg1=None):
            return f"{arg1}-{arg2}-{kwarg1}"

        result = test_func("a", "b", kwarg1="c")
        assert result == "a-b-c"

    def test_wrap_in_api_client_exception_logging(self):
        """Test that exceptions are logged."""
        @wrap_in_api_client
        def test_func():
            raise RuntimeError("Test runtime error")

        with patch('scheduler.tui.utils.logger', autospec=True) as mock_logger:
            result = test_func()
            assert result is None
            mock_logger.error.assert_called_once()
            assert "API error in test_func" in mock_logger.error.call_args[0][0]
            assert "Test runtime error" in mock_logger.error.call_args[0][0]

    def test_wrap_in_api_client_preserves_function_metadata(self):
        """Test that wrapper preserves function metadata."""
        @wrap_in_api_client
        def test_func():
            """Test function docstring."""
            return "test"

        assert test_func.__name__ == "test_func"
        assert test_func.__doc__ == "Test function docstring."
