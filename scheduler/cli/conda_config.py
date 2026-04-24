"""CLI commands for managing conda environment configuration."""
import os
import click
from typing import Optional

from scheduler.core import (
    Config,
    CondaConfig,
    find_workspace_root,
    load_config,
    save_config,
)


@click.group(name='conda-env')
def conda_env_group():
    """Manage conda environment mappings for workspaces.

    Examples:
        # Set conda env for current workspace
        cd /home/user/myproject
        scheduler config conda-env set ml-env

        # Show conda env for current workspace
        scheduler config conda-env show

        # List all mappings
        scheduler config conda-env list
    """
    pass


@conda_env_group.command(name='set')
@click.argument('env_name')
@click.option('--path', default=None, help='Workspace path (default: current directory)')
def set_conda_env(env_name: str, path: Optional[str]):
    """Set conda environment for a workspace.

    This command associates a conda environment with a workspace directory.
    When you submit jobs from this workspace (or its subdirectories), they
    will automatically use the specified conda environment.

    ENV_NAME: Name of the conda environment to use

    Examples:
        # Set conda env for current directory's workspace
        scheduler config conda-env set ml-env

        # Set conda env for specific path
        scheduler config conda-env set pytorch-gpu --path /home/user/project
    """
    # Determine workspace root
    if path is None:
        from scheduler.core import get_logical_cwd
        path = get_logical_cwd()

    try:
        workspace_root = find_workspace_root(path)
    except Exception as e:
        click.echo(f"Error: Could not determine workspace root: {e}", err=True)
        return 1

    # Load current config
    config = load_config()

    # Update conda envs mapping (config is frozen, so create new one)
    envs = dict(config.conda.envs)
    envs[workspace_root] = env_name

    new_conda_config = CondaConfig(
        command=config.conda.command,
        envs=envs
    )

    new_config = Config(
        address=config.address,
        head=config.head,
        worker=config.worker,
        storage=config.storage,
        client=config.client,
        conda=new_conda_config
    )

    # Save config
    save_config(new_config)

    click.echo(f"Set conda environment for workspace:")
    click.echo(f"  Workspace: {workspace_root}")
    click.echo(f"  Conda env: {env_name}")
    return 0


@conda_env_group.command(name='unset')
@click.option('--path', default=None, help='Workspace path (default: current directory)')
def unset_conda_env(path: Optional[str]):
    """Remove conda environment mapping for workspace.

    Examples:
        # Remove conda env for current directory's workspace
        scheduler config conda-env unset

        # Remove conda env for specific path
        scheduler config conda-env unset --path /home/user/project
    """
    if path is None:
        from scheduler.core import get_logical_cwd
        path = get_logical_cwd()

    try:
        workspace_root = find_workspace_root(path)
    except Exception as e:
        click.echo(f"Error: Could not determine workspace root: {e}", err=True)
        return 1

    config = load_config()
    envs = dict(config.conda.envs)

    if workspace_root in envs:
        env_name = envs[workspace_root]
        del envs[workspace_root]

        new_conda_config = CondaConfig(command=config.conda.command, envs=envs)
        new_config = Config(
            address=config.address,
            head=config.head,
            worker=config.worker,
            storage=config.storage,
            client=config.client,
            conda=new_conda_config
        )
        save_config(new_config)

        click.echo(f"Removed conda environment mapping:")
        click.echo(f"  Workspace: {workspace_root}")
        click.echo(f"  Was using: {env_name}")
        return 0
    else:
        click.echo(f"No conda environment mapping found for workspace: {workspace_root}")
        return 1


@conda_env_group.command(name='list')
def list_conda_envs():
    """List all workspace-to-conda-env mappings.

    Shows all configured conda environment mappings across all workspaces.

    Examples:
        scheduler config conda-env list
    """
    config = load_config()

    if not config.conda.envs:
        click.echo("No conda environment mappings configured.")
        click.echo("")
        click.echo("To set a conda environment for a workspace, run:")
        click.echo("  scheduler config conda-env set <env-name>")
        return 0

    click.echo("Conda Environment Mappings:")
    click.echo("=" * 70)
    for workspace, env_name in sorted(config.conda.envs.items()):
        click.echo(f"{workspace}")
        click.echo(f"  → {env_name}")
        click.echo("")
    return 0


@conda_env_group.command(name='show')
@click.option('--path', default=None, help='Workspace path (default: current directory)')
def show_conda_env(path: Optional[str]):
    """Show conda environment for current or specified workspace.

    Examples:
        # Show conda env for current directory's workspace
        scheduler config conda-env show

        # Show conda env for specific path
        scheduler config conda-env show --path /home/user/project
    """
    if path is None:
        from scheduler.core import get_logical_cwd
        path = get_logical_cwd()

    try:
        workspace_root = find_workspace_root(path)
    except Exception as e:
        click.echo(f"Error: Could not determine workspace root: {e}", err=True)
        return 1

    config = load_config()
    env_name = config.conda.envs.get(workspace_root)

    click.echo(f"Workspace: {workspace_root}")
    if env_name:
        click.echo(f"Conda Environment: {env_name}")
    else:
        click.echo("Conda Environment: <not configured>")
        click.echo("")
        click.echo("To set a conda environment for this workspace, run:")
        click.echo(f"  scheduler config conda-env set <env-name>")
    return 0
