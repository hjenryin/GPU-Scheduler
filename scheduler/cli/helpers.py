"""
Helper functions for CLI commands.
"""
import click
from scheduler.core.head_info import load_head_info


def check_head_address_or_prompt():
    """
    Check if head node address is available, and prompt user if not.
    
    Returns:
        True if address is available, False if not
    """
    address = load_head_info()
    
    if not address:
        click.echo("❌ Error: Cannot find head node address")
        click.echo("\nThis typically means you haven't connected to a scheduler cluster yet.")
        click.echo("\nTo resolve this:")
        click.echo("  1. Start a head node: scheduler start --head")
        click.echo("  2. Or connect to an existing head: scheduler start --address=hostname:port")
        click.echo("\nExample: scheduler start --address=turing1:8266")
        return False
    
    return True

