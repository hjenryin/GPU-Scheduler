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
        target: GPU target string (e.g., "node1:GPU0", "node1:0", "node1:0-3", "node1:*")

    Returns:
        Tuple of (node_name, gpu_id_or_range) where gpu_id_or_range can be:
        - An integer for a single GPU
        - A string for a range like "0-3"
        - "*" for all GPUs on the node

    Raises:
        ValueError: If target string is invalid
    """
    if ':' not in target:
        raise ValueError(f"Invalid target format: {target}. Use format like 'node1:GPU0', 'node1:0', 'node1:0-3', or 'node1:*'")

    parts = target.split(':', 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid target format: {target}. Use format like 'node1:GPU0', 'node1:0', 'node1:0-3', or 'node1:*'")

    node_name = parts[0].strip()
    gpu_str = parts[1].strip()

    # Handle wildcard for all GPUs on the node
    if gpu_str == '*':
        return node_name, '*'
    
    # Check for range syntax (e.g., "0-3")
    if '-' in gpu_str:
        range_parts = gpu_str.split('-', 1)
        if len(range_parts) == 2:
            try:
                start_gpu = int(range_parts[0].strip())
                end_gpu = int(range_parts[1].strip())
                if start_gpu < 0 or end_gpu < 0 or start_gpu > end_gpu:
                    raise ValueError(f"Invalid GPU range: {gpu_str}. Range must be non-negative and start <= end")
                return node_name, f"{start_gpu}-{end_gpu}"
            except ValueError as ve:
                if "invalid literal" in str(ve):
                    raise ValueError(f"Invalid GPU range format: {gpu_str}. Must be two numbers separated by '-'.")
                else:
                    raise ve

    # Remove "GPU" prefix if present
    if gpu_str.upper().startswith('GPU'):
        gpu_str = gpu_str[3:]

    try:
        gpu_id = int(gpu_str)
    except ValueError:
        raise ValueError(f"Invalid GPU ID: {gpu_str}. Must be a number, '*', or a range (e.g., 0-3)")

    return node_name, gpu_id


def validate_node_exists(node_name: str, client: SchedulerClient) -> bool:
    """
    Validate that the given node name exists in the cluster.

    Args:
        node_name: Name of the node to validate
        client: Scheduler client to check nodes

    Returns:
        True if node exists and is connected, False otherwise
    """
    try:
        # Get all nodes and check if the specified node exists
        nodes = client.list_nodes()
        for node in nodes:
            if node.node_name == node_name:
                # Optionally, we can check if the node is connected
                # Return True if node exists (regardless of connection status)
                return True
        return False
    except Exception:
        # If we can't connect to get the list of nodes, return False
        return False


def freeze_command(target: str, duration: str) -> int:
    """
    Freeze a GPU for a specified duration.

    Args:
        target: GPU target (e.g., "node1:GPU0", "node1:0", "node1:0-3", "node1:*")
        duration: Duration string (e.g., "12h", "30m", "2d")

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        NodeNotFoundException: If node not found
    """
    try:
        # Parse target
        node_name, gpu_id_or_range = parse_gpu_target(target)

        # Parse duration
        duration_seconds = parse_duration(duration)

        # Create client and check if node exists
        config = load_config()
        client = SchedulerClient(config=config)

        # Validate that the node exists
        if not validate_node_exists(node_name, client):
            if node_name != '*':  # Don't validate '*' wildcard
                raise NodeNotFoundException(f"Node '{node_name}' does not exist in the cluster")
        
        # Handle different target types
        if gpu_id_or_range == '*':
            # Freeze all GPUs on the node
            try:
                node = client.get_node(node_name)
                gpu_ids = list(range(node.num_gpus))
            except NodeNotFoundException:
                raise NodeNotFoundException(f"Node '{node_name}' does not exist in the cluster")
                
            for gpu_id in gpu_ids:
                response = client.freeze_gpu(node_name, gpu_id, duration_seconds)
                click.echo(f"✓ GPU {gpu_id} on node {node_name} frozen for {duration}")
                if response.get('frozen_until'):
                    click.echo(f"  Frozen until: {response['frozen_until']}")
        elif isinstance(gpu_id_or_range, str) and '-' in gpu_id_or_range:
            # Handle range syntax (e.g., "0-3")
            start_gpu, end_gpu = map(int, gpu_id_or_range.split('-'))
            for gpu_id in range(start_gpu, end_gpu + 1):
                response = client.freeze_gpu(node_name, gpu_id, duration_seconds)
                click.echo(f"✓ GPU {gpu_id} on node {node_name} frozen for {duration}")
                if response.get('frozen_until'):
                    click.echo(f"  Frozen until: {response['frozen_until']}")
        else:
            # Handle single GPU
            gpu_id = gpu_id_or_range
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