from datetime import timedelta
from typing import Optional
def format_gpu_memory(bytes_val: int) -> str:
    """
    Format GPU memory for display.

    Args:
        bytes_val: Memory in bytes
        
    Returns:
        Formatted string (e.g., "12.5 GB")
    """
    pass


def get_status_color(status: str) -> str:
    """
    Get color for a status string.

    Args:
        status: Status string (e.g., "running", "failed")
        
    Returns:
        Textual color name (e.g., "green", "red")
    """
    pass


def format_runtime(runtime: Optional[timedelta]) -> str:
    """
    Format runtime for display.

    Args:
        runtime: Runtime duration
        
    Returns:
        Formatted string (e.g., "01:23:45" or "-")
    """
    pass


def create_gpu_utilization_bar(utilization: float, width: int = 20) -> str:
    """
    Create ASCII bar for GPU utilization.

    Args:
        utilization: Utilization percentage (0-100)
        width: Bar width in characters
        
    Returns:
        ASCII bar string (e.g., "████████░░ 82%")
    """
    pass


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
    pass
