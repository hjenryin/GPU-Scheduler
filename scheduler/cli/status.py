from scheduler.core import load_config
from scheduler.api import SchedulerClient
from scheduler.tui import run_tui
import logging
import click

logger = logging.getLogger(__name__)


def status_command() -> int:
    """
    Launch interactive TUI for cluster monitoring.

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
    """
    try:
        # Load configuration
        config = load_config()

        # Get head node address from config or use default
        address = config.address if config.address else f'localhost:{config.head.port}'

        # Create client and run TUI
        client = SchedulerClient(address=address, config=config)

        # Test connection before launching TUI
        try:
            client.list_nodes()
        except Exception as e:
            click.echo(f"Error: Cannot connect to head node at {address}")
            click.echo(f"Details: {e}")
            click.echo("\nMake sure the head node is running:")
            click.echo("  scheduler start --head")
            return 1

        # Launch TUI
        run_tui(client=client)
        return 0

    except KeyboardInterrupt:
        click.echo("\nExiting...")
        return 0
    except Exception as e:
        logger.error(f"Error launching TUI: {e}")
        click.echo(f"Error: {e}")
        return 1
