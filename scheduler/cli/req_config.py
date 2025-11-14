"""CLI commands for managing requirement shortcuts configuration."""
import click
from typing import Optional

from scheduler.core import (
    Config,
    ClientConfig,
    load_config,
    save_config,
)


@click.group(name='req-config')
def req_config_group():
    """Manage requirement shortcuts for job submissions.

    Examples:
        # Set a shortcut named 'train' for GPU requirements
        scheduler config req-config set train node1:4,node2:8

        # Submit a job using the shortcut
        scheduler submit --req train python train.py

        # List all shortcuts
        scheduler config req-config list

        # Show a specific shortcut
        scheduler config req-config show train
    """
    pass


@req_config_group.command(name='set')
@click.argument('name')
@click.argument('requirements')
def set_req_shortcut(name: str, requirements: str):
    """Set a requirement shortcut.

    This command creates a named shortcut for GPU requirements that can be
    used when submitting jobs with --req.

    NAME: Shortcut name
    REQUIREMENTS: GPU requirement string (e.g., "node1:4,node2:8", "4", "gpu1")

    Examples:
        # Set a shortcut for training jobs
        scheduler config req-config set train node1:4,node2:8

        # Set a shortcut for inference jobs
        scheduler config req-config set inference gpu2:2

        # Set a shortcut for small jobs
        scheduler config req-config set small 1
    """
    # Load current config
    config = load_config()

    # Update req_shortcuts mapping (config is frozen, so create new one)
    shortcuts = dict(config.client.req_shortcuts)
    shortcuts[name] = requirements

    new_client_config = ClientConfig(
        default_req=config.client.default_req,
        req_shortcuts=shortcuts
    )

    new_config = Config(
        address=config.address,
        head=config.head,
        worker=config.worker,
        storage=config.storage,
        client=new_client_config,
        conda=config.conda
    )

    # Save config
    save_config(new_config)

    click.echo(f"Set requirement shortcut:")
    click.echo(f"  Name: {name}")
    click.echo(f"  Requirements: {requirements}")
    return 0


@req_config_group.command(name='unset')
@click.argument('name')
def unset_req_shortcut(name: str):
    """Remove a requirement shortcut.

    NAME: Shortcut name to remove

    Examples:
        # Remove the 'train' shortcut
        scheduler config req-config unset train
    """
    config = load_config()
    shortcuts = dict(config.client.req_shortcuts)

    if name in shortcuts:
        requirements = shortcuts[name]
        del shortcuts[name]

        new_client_config = ClientConfig(
            default_req=config.client.default_req,
            req_shortcuts=shortcuts
        )
        new_config = Config(
            address=config.address,
            head=config.head,
            worker=config.worker,
            storage=config.storage,
            client=new_client_config,
            conda=config.conda
        )
        save_config(new_config)

        click.echo(f"Removed requirement shortcut:")
        click.echo(f"  Name: {name}")
        click.echo(f"  Was: {requirements}")
        return 0
    else:
        click.echo(f"No requirement shortcut found with name: {name}")
        return 1


@req_config_group.command(name='list')
def list_req_shortcuts():
    """List all requirement shortcuts.

    Shows all configured requirement shortcuts.

    Examples:
        scheduler config req-config list
    """
    config = load_config()

    if not config.client.req_shortcuts:
        click.echo("No requirement shortcuts configured.")
        click.echo("")
        click.echo("To set a requirement shortcut, run:")
        click.echo("  scheduler config req-config set <name> <requirements>")
        return 0

    click.echo("Requirement Shortcuts:")
    click.echo("=" * 70)
    for name, requirements in sorted(config.client.req_shortcuts.items()):
        click.echo(f"{name}")
        click.echo(f"  → {requirements}")
        click.echo("")
    return 0


@req_config_group.command(name='show')
@click.argument('name')
def show_req_shortcut(name: str):
    """Show a specific requirement shortcut.

    NAME: Shortcut name to display

    Examples:
        # Show the 'train' shortcut
        scheduler config req-config show train
    """
    config = load_config()
    requirements = config.client.req_shortcuts.get(name)

    if requirements:
        click.echo(f"Requirement Shortcut: {name}")
        click.echo(f"  Requirements: {requirements}")
    else:
        click.echo(f"No requirement shortcut found with name: {name}")
        click.echo("")
        click.echo("To set this shortcut, run:")
        click.echo(f"  scheduler config req-config set {name} <requirements>")
        return 1
    return 0
