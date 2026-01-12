import click
import re

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, NodeNotFoundException
from scheduler.cli.freeze import parse_gpu_target, validate_node_exists


def unfreeze_command(target: str = None) -> int:
    """
    Unfreeze GPU(s).

    Args:
        target: GPU target (e.g., "node1:GPU0", "node1:0", "node1:0-3", "node1:*"). If None, unfreezes all GPUs.

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        NodeNotFoundException: If node not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        if target is None:
            # Unfreeze all GPUs
            response = client.unfreeze_all_gpus()
            unfrozen_count = response.get('unfrozen_count', 0)

            if unfrozen_count == 0:
                click.echo("No GPUs were frozen")
            elif unfrozen_count == 1:
                click.echo("✓ Unfroze 1 GPU")
            else:
                click.echo(f"✓ Unfroze {unfrozen_count} GPUs")
        else:
            # Unfreeze specific GPU(s)
            node_name, gpu_id_or_range = parse_gpu_target(target)

            # Validate that the node exists
            if not validate_node_exists(node_name, client):
                if node_name != '*':  # Don't validate '*' wildcard
                    raise NodeNotFoundException(f"Node '{node_name}' does not exist in the cluster")

            if gpu_id_or_range == '*':
                # Unfreeze all GPUs on the node
                try:
                    node = client.get_node(node_name)
                    gpu_ids = list(range(node.num_gpus))
                except NodeNotFoundException:
                    raise NodeNotFoundException(f"Node '{node_name}' does not exist in the cluster")
                    
                for gpu_id in gpu_ids:
                    response = client.unfreeze_gpu(node_name, gpu_id)
                    click.echo(f"✓ GPU {gpu_id} on node {node_name} unfrozen")
            elif isinstance(gpu_id_or_range, str) and '-' in gpu_id_or_range:
                # Handle range syntax (e.g., "0-3")
                start_gpu, end_gpu = map(int, gpu_id_or_range.split('-'))
                for gpu_id in range(start_gpu, end_gpu + 1):
                    response = client.unfreeze_gpu(node_name, gpu_id)
                    click.echo(f"✓ GPU {gpu_id} on node {node_name} unfrozen")
            else:
                # Handle single GPU
                gpu_id = gpu_id_or_range
                response = client.unfreeze_gpu(node_name, gpu_id)
                click.echo(f"✓ GPU {gpu_id} on node {node_name} unfrozen")

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