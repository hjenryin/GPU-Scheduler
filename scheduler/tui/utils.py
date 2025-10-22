from datetime import timedelta
from typing import Optional
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def format_gpu_memory(bytes_val: int) -> str:
    """
    Format GPU memory for display.

    Args:
        bytes_val: Memory in bytes

    Returns:
        Formatted string (e.g., "12.5 GB")
    """
    gb = bytes_val / (1024 ** 3)
    return f"{gb:.1f}G"


def get_status_color(status: str) -> str:
    """
    Get color for a status string.

    Args:
        status: Status string (e.g., "running", "failed")

    Returns:
        Textual color name (e.g., "green", "red")
    """
    status_colors = {
        "pending": "yellow",
        "running": "green",
        "completed": "blue",
        "failed": "red",
        "cancelled": "gray",
        "connected": "green",
        "disconnected": "red",
    }
    return status_colors.get(status.lower(), "white")


def format_runtime(runtime: Optional[timedelta]) -> str:
    """
    Format runtime for display.

    Args:
        runtime: Runtime duration

    Returns:
        Formatted string (e.g., "01:23:45" or "-")
    """
    if runtime is None:
        return "-"

    total_seconds = int(runtime.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def create_gpu_utilization_bar(utilization: float, width: int = 20) -> str:
    """
    Create ASCII bar for GPU utilization.

    Args:
        utilization: Utilization percentage (0-100)
        width: Bar width in characters

    Returns:
        ASCII bar string (e.g., "████████░░ 82%")
    """
    filled = int((utilization / 100.0) * width)
    empty = width - filled
    bar = "█" * filled + "░" * empty
    return f"{bar} {utilization:3.0f}%"


def wrap_in_api_client(func):
    """
    Decorator to handle API client exceptions in TUI.

    Catches ConnectionException and other API errors,
    displays error message to user, and handles gracefully.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"API error in {func.__name__}: {e}")
            # Return None or empty data depending on context
            return None

    return wrapper
