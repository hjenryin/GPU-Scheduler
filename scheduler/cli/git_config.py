"""CLI commands for managing git snapshot configuration."""
import click
import yaml

from scheduler.core import (
    Config,
    load_config,
    save_config,
    parse_size,
    ValidationException,
)


@click.group(name='git-config')
def git_config_group():
    """Manage Git Snapshot limits and inclusions.
    
    Examples:
        # Set max file size for a specific extension
        scheduler config git-config set data_type_limits.json 512k
        
        # Set absolute maximum file size
        scheduler config git-config set max_file_size 5m
        
        # Add an extension to always be included
        scheduler config git-config set always_include_extensions .txt,.yaml
    """
    pass


@git_config_group.command(name='set')
@click.argument('key')
@click.argument('value')
def set_git_config(key: str, value: str):
    """Set a git snapshot config value.
    
    Supported keys:
      max_file_size                  (e.g., 5m)
      max_files_per_folder           (e.g., 1000)
      data_type_limits.<ext>         (e.g., data_type_limits.json 512k)
      always_include_extensions      (e.g., .txt,.csv)
      exclude_patterns               (e.g., *.log,tmp/)
    """
    config = load_config()
    config_dict = config.to_dict() if hasattr(config, 'to_dict') else config
    
    snapshot_dict = config_dict.setdefault('snapshot', {})
    
    try:
        if key == 'max_file_size':
            snapshot_dict[key] = parse_size(value)
            
        elif key == 'max_files_per_folder':
            snapshot_dict[key] = int(value)
            
        elif key.startswith('data_type_limits.'):
            ext = key.split('.', 1)[1]
            dt_dict = snapshot_dict.setdefault('data_type_limits', {})
            dt_dict[ext] = parse_size(value)
            
        elif key in ['always_include_extensions', 'exclude_patterns']:
            try:
                parsed_list = yaml.safe_load(value)
                if not isinstance(parsed_list, list):
                    parsed_list = [v.strip() for v in value.split(',')]
                snapshot_dict[key] = parsed_list
            except yaml.YAMLError:
                snapshot_dict[key] = [v.strip() for v in value.split(',')]
                
        else:
            click.echo(f"Error: Unknown or unsupported git-config key '{key}'")
            return 1
    except ValidationException as e:
        click.echo(f"Error: {e}")
        return 2
    except ValueError as e:
        click.echo(f"Error parsing value: {e}")
        return 2
        
    new_config = Config.from_dict(config_dict)
    save_config(new_config)
    click.echo(f"Set git-config {key} = {value}")
    return 0


@git_config_group.command(name='get')
@click.argument('key')
def get_git_config(key: str):
    """Get a git snapshot config value.
    
    Supported keys are exactly as in 'set'.
    """
    config = load_config()
    snapshot_dict = config.to_dict().get('snapshot', {})
    
    if key.startswith('data_type_limits.'):
        ext = key.split('.', 1)[1]
        val = snapshot_dict.get('data_type_limits', {}).get(ext)
    else:
        val = snapshot_dict.get(key)
        
    if val is not None:
        click.echo(val)
        return 0
    else:
        click.echo(f"Key '{key}' not configured or empty.", err=True)
        return 1

@git_config_group.command(name='list')
def list_git_config():
    """List all Git Snapshot settings."""
    config = load_config()
    snapshot_dict = config.to_dict().get('snapshot', {})
    click.echo("Git Snapshot Configuration:")
    click.echo("=" * 40)
    for k, v in snapshot_dict.items():
        if isinstance(v, dict):
            click.echo(f"{k}:")
            for sub_k, sub_v in v.items():
                click.echo(f"  {sub_k}: {sub_v}")
        else:
            click.echo(f"{k}: {v}")
    return 0
