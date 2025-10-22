from scheduler.core.config import load_config
from scheduler.api.client import SchedulerClient
from scheduler.tui.app import run_tui
import logging

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

        # Get head node address
        address = config.get('head', {}).get('address', 'localhost:8265')

        # Create client and run TUI
        client = SchedulerClient(address=address, config=config)

        # Test connection before launching TUI
        try:
            client.list_nodes()
        except Exception as e:
            print(f"Error: Cannot connect to head node at {address}")
            print(f"Details: {e}")
            print("\nMake sure the head node is running:")
            print("  scheduler start --head")
            return 1

        # Launch TUI
        run_tui(client=client)
        return 0

    except KeyboardInterrupt:
        print("\nExiting...")
        return 0
    except Exception as e:
        logger.error(f"Error launching TUI: {e}")
        print(f"Error: {e}")
        return 1
