import yaml
from typing import Optional
import click

from scheduler.core import load_config, save_config, init_config, Config
from scheduler.core import constants


def config_command(
    command: str,
    key: Optional[str] = None,
    value: Optional[str] = None,
    config_file: Optional[str] = None
) -> int:
    """
    Manage scheduler configuration.

    Args:
        command: Subcommand ("init", "show", "get", "set")
        key: Configuration key (for get/set)
        value: Configuration value (for set)
        config_file: Path to config file

    Returns:
        Exit code (0 for success)

    Raises:
        ValidationException: If arguments are invalid
        FileNotFoundError: If config file not found (for show/get)
    """
    try:
        if command == "init":
            init_config()
            click.echo(f"Configuration initialized at {constants.CONFIG_FILE_PATH}")
            return 0

        elif command == "show":
            config = load_config()
            # Convert Config object to dict for display
            config_dict = config.to_dict() if hasattr(config, 'to_dict') else config
            click.echo(yaml.dump(config_dict, default_flow_style=False))
            return 0

        elif command == "get":
            if not key:
                click.echo("Error: key required for 'get' command")
                return 2
            config = load_config()
            # Convert Config object to dict
            config_dict = config.to_dict() if hasattr(config, 'to_dict') else config
            # Support nested keys with dots: head.port or head_node.port
            keys = key.split('.')
            value_out = config_dict
            for k in keys:
                if isinstance(value_out, dict):
                    value_out = value_out.get(k, {})
                else:
                    value_out = {}
                    break
            click.echo(value_out if value_out else "")
            return 0 if value_out else 1

        elif command == "set":
            if not key or value is None:
                click.echo("Error: key and value required for 'set' command")
                return 2
            config = load_config()
            # Convert Config object to dict
            config_dict = config.to_dict() if hasattr(config, 'to_dict') else config
            # Support nested keys
            keys = key.split('.')
            current = config_dict
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            # Parse value through yaml to get original type correctly
            try:
                parsed_value = yaml.safe_load(value)
            except yaml.YAMLError:
                parsed_value = value
                
            current[keys[-1]] = parsed_value
            
            # Reconstruct Config and validate
            if hasattr(Config, 'from_dict'):
                new_config = Config.from_dict(config_dict)
                save_config(new_config)
            else:
                save_config(config_dict)
                
            click.echo(f"Set {key} = {value}")
            return 0

        else:
            click.echo(f"Error: Unknown command '{command}'")
            click.echo("Valid commands: init, show, get, set")
            return 2

    except FileNotFoundError:
        click.echo(f"Config file not found. Run 'scheduler config init' to create one.")
        return 4
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
