import click

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, NodeNotFoundException
from scheduler.cli.freeze import parse_gpu_target


def unfreeze_command(target: str = None) -> int:
    """
    Unfreeze GPU(s).

    Args:
        target: GPU target (e.g., "node1:GPU0", "node1:0"). If None, unfreezes all GPUs.

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
            # Unfreeze specific GPU
            node_name, gpu_id = parse_gpu_target(target)
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
