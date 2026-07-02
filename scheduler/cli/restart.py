import logging
from typing import Optional

import click

from scheduler.api import SchedulerClient
from scheduler.core import ConnectionException, load_config

logger = logging.getLogger(__name__)


def restart_command(timeout: Optional[int] = None) -> int:
    """Request a cluster restart from the head node."""
    try:
        config = load_config()
        if timeout is None:
            timeout = max(10, 2 * config.worker.heartbeat_interval)

        client = SchedulerClient(config=config)
        try:
            result = client.restart_cluster(timeout=timeout)
        finally:
            client.close()

        status = result.get("status", "unknown")
        restart_id = result.get("restart_id")
        click.echo(f"Restart {restart_id}: {status}")

        acked_nodes = result.get("acked_nodes", [])
        rejoined_nodes = result.get("rejoined_nodes", [])
        missing_nodes = result.get("missing_nodes", [])

        click.echo(f"Workers acknowledged: {len(acked_nodes)}")
        click.echo(f"Workers rejoined: {len(rejoined_nodes)}")

        if missing_nodes:
            click.echo(click.style("✗", fg="red") + " Some workers did not join")
            click.echo("Missing workers:")
            for node_name in missing_nodes:
                click.echo(f"  - {node_name}")

        if result.get("head_restart_scheduled"):
            click.echo(click.style("✓", fg="green") + " Head restart scheduled")
            return 0
        else:
            click.echo("Head restart skipped")
            return 1
    except ConnectionException as e:
        click.echo(f"Error: Cannot request cluster restart: {e}")
        click.echo("Make sure the head node is running and accessible")
        return 1
    except Exception as e:
        logger.error(f"Error restarting cluster: {e}", exc_info=True)
        click.echo(f"Error: {e}")
        return 1
