import yaml
from typing import Optional

from scheduler.core.config import load_config, save_config, init_config
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
            print(f"Configuration initialized at {constants.CONFIG_FILE_PATH}")
            return 0

        elif command == "show":
            config = load_config()
            print(yaml.dump(config, default_flow_style=False))
            return 0

        elif command == "get":
            if not key:
                print("Error: key required for 'get' command")
                return 2
            config = load_config()
            # Support nested keys with dots: head_node.port
            keys = key.split('.')
            value_out = config
            for k in keys:
                value_out = value_out.get(k, {})
            print(value_out if value_out else "")
            return 0

        elif command == "set":
            if not key or value is None:
                print("Error: key and value required for 'set' command")
                return 2
            config = load_config()
            # Support nested keys
            keys = key.split('.')
            current = config
            for k in keys[:-1]:
                current = current.setdefault(k, {})
            current[keys[-1]] = value
            save_config(config)
            print(f"Set {key} = {value}")
            return 0

        else:
            print(f"Error: Unknown command '{command}'")
            print("Valid commands: init, show, get, set")
            return 2

    except FileNotFoundError:
        print(f"Config file not found. Run 'scheduler config init' to create one.")
        return 4
    except Exception as e:
        print(f"Error: {e}")
        return 1
