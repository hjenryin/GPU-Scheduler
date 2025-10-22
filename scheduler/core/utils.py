from datetime import datetime, timedelta
from typing import List, Tuple, Optional

from scheduler.core.exceptions import InvalidRequirementException
from scheduler.core.models import JobRequirement


def parse_requirements(req_str: str) -> List[Tuple[Optional[str], int]]:
    """
    Parse requirement string into list of alternatives.

    Args:
        req_str: Requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")
        
    Returns:
        List of (node_name, num_gpus) tuples. node_name is None for any node.
        
    Raises:
        InvalidRequirementException: If requirement string is invalid
    
    Examples:
        parse_requirements("2") -> [(None, 2)]
        parse_requirements("gpu1:4") -> [("gpu1", 4)]
        parse_requirements("gpu1:2,gpu2:4") -> [("gpu1", 2), ("gpu2", 4)]
    """
    pass


def format_duration(duration: timedelta) -> str:
    """
    Format duration as human-readable string.

    Args:
        duration: Duration to format
        
    Returns:
        Formatted string (e.g., "01:23:45", "5d 03:22:11")
    """
    pass


def format_timestamp(dt: datetime, relative: bool = False) -> str:
    """
    Format timestamp as human-readable string.

    Args:
        dt: Datetime to format
        relative: If True, return relative time (e.g., "2 hours ago")
        
    Returns:
        Formatted timestamp string
    """
    pass


def format_bytes(bytes_val: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB", "256 MB")
    """
    pass


def generate_job_id() -> str:
    """
    Generate unique job ID.

    Returns:
        Job ID string in format "job_<uuid>"
    """
    pass


def generate_versioned_filename(script_path: str, job_id: str) -> str:
    """
    Generate versioned filename for script.

    Args:
        script_path: Original script path
        job_id: Job ID
        
    Returns:
        Versioned filename (e.g., "script.py.scheduler_job_abc123_hash.py")
    """
    pass


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check
        host: Host address to bind to
        
    Returns:
        True if port is available
    """
    pass


def get_local_ip() -> str:
    """
    Get local IP address of this machine.

    Returns:
        IP address string
    """
    pass


def ensure_dir_exists(path: str):
    """
    Ensure directory exists, create if it doesn't.

    Args:
        path: Directory path
        
    Raises:
        PermissionDeniedException: If cannot create directory
    """
    pass


def parse_address(address: str) -> Tuple[str, int]:
    """
    Parse address string into host and port.

    Args:
        address: Address string (e.g., "host:port" or "host")
        
    Returns:
        Tuple of (host, port)
        
    Raises:
        ValidationException: If address format is invalid
    """
    pass
