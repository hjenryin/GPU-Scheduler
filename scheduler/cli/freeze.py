import click
import re

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, NodeNotFoundException


def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to seconds.

    Args:
        duration_str: Duration string (e.g., "12h", "30m", "2d", "3600s")

    Returns:
        Duration in seconds

    Raises:
        ValueError: If duration string is invalid
    """
    # Match pattern like "12h", "30m", "2d", "3600s", "5w"
    match = re.match(r'^(\d+)([smhdw])$', duration_str.lower())
    if not match:
        raise ValueError(f"Invalid duration format: {duration_str}. Use format like 12h, 30m, 2d, 3600s, 5w")

    value, unit = match.groups()
    value = int(value)

    # Convert to seconds
    multipliers = {
        's': 1,           # seconds
        'm': 60,          # minutes
        'h': 3600,        # hours
        'd': 86400,       # days
        'w': 604800,      # weeks
    }

    return value * multipliers[unit]


def parse_gpu_target(target: str) -> tuple:
    """
    Parse GPU target string.

    Args:
        target: GPU target string (e.g., "node1:GPU0", "node1:0")

    Returns:
        Tuple of (node_name, gpu_id)

    Raises:
        ValueError: If target string is invalid
    """
    if ':' not in target:
        raise ValueError(f"Invalid target format: {target}. Use format like 'node1:GPU0' or 'node1:0'")

    parts = target.split(':', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid target format: {target}. Use format like 'node1:GPU0' or 'node1:0'")

    node_name = parts[0].strip()
    gpu_str = parts[1].strip()

    # Remove "GPU" prefix if present
    if gpu_str.upper().startswith('GPU'):
        gpu_str = gpu_str[3:]

    try:
        gpu_id = int(gpu_str)
    except ValueError:
        raise ValueError(f"Invalid GPU ID: {gpu_str}. Must be a number (e.g., 0, 1, 2)")

    return node_name, gpu_id


def freeze_command(target: str, duration: str) -> int:
    """
    Freeze a GPU for a specified duration.

    Args:
        target: GPU target (e.g., "node1:GPU0", "node1:0")
        duration: Duration string (e.g., "12h", "30m", "2d")

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        NodeNotFoundException: If node not found
    """
    try:
        # Parse target
        node_name, gpu_id = parse_gpu_target(target)

        # Parse duration
        duration_seconds = parse_duration(duration)

        # Create client and freeze GPU
        config = load_config()
        client = SchedulerClient(config=config)

        response = client.freeze_gpu(node_name, gpu_id, duration_seconds)

        # Display success message
        click.echo(f"✓ GPU {gpu_id} on node {node_name} frozen for {duration}")
        if response.get('frozen_until'):
            click.echo(f"  Frozen until: {response['frozen_until']}")

        return 0

    except ValueError as e:
        click.echo(f"❌ Invalid input: {e}")
        return 1
    except NodeNotFoundException as e:
        click.echo(f"❌ {e}")
        return 1
    except ConnectionException as e:
        click.echo(f"❌ Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"❌ Error: {e}")
        return 1
