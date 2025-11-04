from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import os
import socket
import hashlib
import uuid
import pathlib

from scheduler.core.exceptions import InvalidRequirementException, PermissionDeniedException, ValidationException


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
    if not req_str or not req_str.strip():
        raise InvalidRequirementException("Requirement string cannot be empty")

    alternatives = []
    # Split by comma for alternatives (e.g., "gpu1:2,gpu2:4")
    parts = req_str.split(',')

    for part in parts:
        part = part.strip()
        if ':' in part:
            # Node-specific requirement (e.g., "gpu1:4")
            node_gpu = part.split(':', 1)
            if len(node_gpu) != 2:
                raise InvalidRequirementException(f"Invalid requirement format: {part}")
            node_name = node_gpu[0].strip()
            try:
                num_gpus = int(node_gpu[1].strip())
            except ValueError:
                raise InvalidRequirementException(f"Invalid GPU count: {node_gpu[1]}")
            if num_gpus <= 0:
                raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
            alternatives.append((node_name, num_gpus))
        else:
            # Any node requirement (e.g., "2")
            try:
                num_gpus = int(part)
            except ValueError:
                raise InvalidRequirementException(f"Invalid GPU count: {part}")
            if num_gpus <= 0:
                raise InvalidRequirementException(f"GPU count must be positive: {num_gpus}")
            alternatives.append((None, num_gpus))

    return alternatives


def format_duration(duration: timedelta) -> str:
    """
    Format duration as human-readable string.

    Args:
        duration: Duration to format

    Returns:
        Formatted string (e.g., "01:23:45", "5d 03:22:11")
    """
    total_seconds = int(duration.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if days > 0:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_timestamp(dt: datetime, relative: bool = False) -> str:
    """
    Format timestamp as human-readable string.

    Args:
        dt: Datetime to format
        relative: If True, return relative time (e.g., "2 hours ago")

    Returns:
        Formatted timestamp string
    """
    if relative:
        now = datetime.now()
        delta = now - dt

        if delta.total_seconds() < 60:
            return "just now"
        elif delta.total_seconds() < 3600:
            minutes = int(delta.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif delta.total_seconds() < 86400:
            hours = int(delta.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(delta.total_seconds() / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_bytes(bytes_val: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes

    Returns:
        Formatted string (e.g., "1.5 GB", "256 MB")
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(bytes_val)
    unit_idx = 0

    while size >= 1024.0 and unit_idx < len(units) - 1:
        size /= 1024.0
        unit_idx += 1

    if unit_idx == 0:
        return f"{int(size)} {units[unit_idx]}"
    else:
        return f"{size:.1f} {units[unit_idx]}"


def generate_job_id() -> str:
    """
    Generate unique job ID.

    Returns:
        Job ID string in format "job_<uuid>"
    """
    # Use first 16 characters of UUID for shorter IDs
    return f"job_{uuid.uuid4().hex[:16]}"


def generate_versioned_filename(script_path: str, job_id: str) -> str:
    """
    Generate versioned filename for script.

    Args:
        script_path: Original script path
        job_id: Job ID

    Returns:
        Versioned filename (e.g., "script.py.scheduler_job_abc123_hash.py")
    """
    # Get script name and read its content for hashing
    script_name = os.path.basename(script_path)

    # Generate hash from script content if file exists
    try:
        with open(script_path, 'rb') as f:
            content_hash = hashlib.sha256(f.read()).hexdigest()[:8]
    except (FileNotFoundError, PermissionError):
        # If we can't read the file, use timestamp-based hash
        content_hash = hashlib.sha256(str(datetime.now()).encode()).hexdigest()[:8]

    # Split name and extension
    name_parts = script_name.rsplit('.', 1)
    if len(name_parts) == 2:
        base_name, ext = name_parts
        return f"{base_name}.scheduler_{job_id}_{content_hash}.{ext}"
    else:
        return f"{script_name}.scheduler_{job_id}_{content_hash}"


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check
        host: Host address to bind to

    Returns:
        True if port is available
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            return True
    except OSError:
        return False


def find_available_port(start_port: int = 8000, max_attempts: int = 100, host: str = "0.0.0.0") -> int:
    """
    Find an available port starting from a given port.

    Args:
        start_port: Port number to start searching from
        max_attempts: Maximum number of ports to try
        host: Host address to bind to

    Returns:
        Available port number

    Raises:
        PermissionDeniedException: If no available port found
    """
    for port in range(start_port, start_port + max_attempts):
        if is_port_available(port, host):
            return port
    
    raise PermissionDeniedException(
        f"No available port found in range {start_port}-{start_port + max_attempts - 1}"
    )


def get_local_ip() -> str:
    """
    Get local IP address of this machine.

    Returns:
        IP address string
    """
    try:
        # Create a socket to get the local IP
        # This doesn't actually connect, just determines routing
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback to localhost
        return "127.0.0.1"


def ensure_dir_exists(path: str):
    """
    Ensure directory exists, create if it doesn't.

    Args:
        path: Directory path

    Raises:
        PermissionDeniedException: If cannot create directory
    """
    try:
        # Expand user home directory if needed
        expanded_path = os.path.expanduser(path)
        pathlib.Path(expanded_path).mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        raise PermissionDeniedException(f"Cannot create directory {path}: {e}")
    except Exception as e:
        raise PermissionDeniedException(f"Error creating directory {path}: {e}")


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
    if not address or not address.strip():
        raise ValidationException("Address cannot be empty")

    address = address.strip()

    if ':' in address:
        parts = address.rsplit(':', 1)
        if len(parts) != 2:
            raise ValidationException(f"Invalid address format: {address}")

        host = parts[0].strip()
        try:
            port = int(parts[1].strip())
            if port < 1 or port > 65535:
                raise ValidationException(f"Port must be between 1 and 65535: {port}")
        except ValueError:
            raise ValidationException(f"Invalid port number: {parts[1]}")

        return (host, port)
    else:
        # No port specified, return just the host with a default port (will be determined by caller)
        raise ValidationException(f"Address must include port (format: host:port): {address}")


def parse_time_duration(duration_str: str) -> timedelta:
    """
    Parse time duration string into timedelta object.

    Args:
        duration_str: Duration string (e.g., "7d", "3w", "24h", "30m")

    Returns:
        timedelta object

    Raises:
        ValidationException: If duration format is invalid

    Examples:
        parse_time_duration("7d") -> timedelta(days=7)
        parse_time_duration("3w") -> timedelta(weeks=3)
        parse_time_duration("24h") -> timedelta(hours=24)
        parse_time_duration("30m") -> timedelta(minutes=30)
    """
    if not duration_str or not duration_str.strip():
        raise ValidationException("Duration string cannot be empty")

    duration_str = duration_str.strip().lower()

    # Extract number and unit
    import re
    match = re.match(r'^(\d+)([wdhms])$', duration_str)
    if not match:
        raise ValidationException(
            f"Invalid duration format: {duration_str}. "
            "Expected format: <number><unit> where unit is w(weeks), d(days), h(hours), m(minutes), or s(seconds). "
            "Examples: 7d, 3w, 24h, 30m"
        )

    value = int(match.group(1))
    unit = match.group(2)

    if value <= 0:
        raise ValidationException(f"Duration value must be positive: {value}")

    # Convert to timedelta
    if unit == 'w':
        return timedelta(weeks=value)
    elif unit == 'd':
        return timedelta(days=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'm':
        return timedelta(minutes=value)
    elif unit == 's':
        return timedelta(seconds=value)
    else:
        # Should never reach here due to regex
        raise ValidationException(f"Invalid duration unit: {unit}")
