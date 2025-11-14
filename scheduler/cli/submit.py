import os
import time
from typing import List, Optional
import click
from collections import defaultdict

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ValidationException, ConnectionException


def expand_and_sort_requirements(req_str: str) -> str:
    """
    Expand range syntax and sort repeated hosts for backward compatibility.

    This allows using new syntax while keeping the server-side 2-tuple format:
    - Range: "host:4-8" → "host:8,host:7,host:6,host:5,host:4"
    - Repeated hosts: "host:4,host:8" → "host:8,host:4" (sorted large to small)

    The old scheduler tries alternatives in order (first match wins), so by
    expanding ranges and sorting from large to small, we get the same "prefer
    more GPUs" behavior without changing the server.

    Args:
        req_str: Requirement string (may contain ranges and repeated hosts)

    Returns:
        Expanded and sorted requirement string
    """
    if not req_str or not req_str.strip():
        return req_str

    # Group alternatives by node name
    node_options = defaultdict(list)

    parts = req_str.split(',')
    for part in parts:
        part = part.strip()

        if ':' in part:
            # Node-specific requirement
            node_name, gpu_spec = part.split(':', 1)
            node_name = node_name.strip()
            gpu_spec = gpu_spec.strip()

            # Check for range syntax (e.g., "4-8")
            if '-' in gpu_spec:
                range_parts = gpu_spec.split('-', 1)
                if len(range_parts) == 2:
                    try:
                        min_gpus = int(range_parts[0].strip())
                        max_gpus = int(range_parts[1].strip())
                        # Expand range from max to min (descending)
                        for num in range(max_gpus, min_gpus - 1, -1):
                            node_options[node_name].append(num)
                        continue
                    except ValueError:
                        pass  # Not a valid range, treat as-is

            # Fixed count or non-range
            try:
                num_gpus = int(gpu_spec)
                node_options[node_name].append(num_gpus)
            except ValueError:
                # Not a number, keep as-is (might be flexible allocation)
                node_options[node_name].append(gpu_spec)
        else:
            # No colon - could be a number or hostname
            # These don't get sorted/expanded, keep as-is
            node_options[None].append(part)

    # Build expanded requirement string
    result_parts = []

    # First add the "any node" options (None key)
    if None in node_options:
        for option in node_options[None]:
            result_parts.append(str(option))

    # Then add node-specific options, sorted by GPU count descending
    for node_name in sorted(node_options.keys()):
        if node_name is None:
            continue

        options = node_options[node_name]
        # Sort numeric options descending (prefer more GPUs)
        numeric_options = []
        non_numeric_options = []

        for opt in options:
            if isinstance(opt, int):
                numeric_options.append(opt)
            else:
                try:
                    numeric_options.append(int(opt))
                except (ValueError, TypeError):
                    non_numeric_options.append(opt)

        # Sort numeric descending
        numeric_options.sort(reverse=True)

        # Add numeric options first (sorted), then non-numeric
        for num in numeric_options:
            result_parts.append(f"{node_name}:{num}")
        for opt in non_numeric_options:
            result_parts.append(f"{node_name}:{opt}")

    return ','.join(result_parts)


def submit_command(
    command: List[str],
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    working_dir: Optional[str] = None
) -> int:
    """
    Submit a new job to the scheduler.

    Args:
        command: Command to execute as a list (e.g., ['python', 'train.py', '--epochs', '10'])
        req: Resource requirement string
        depends_on: List of job IDs to depend on
        name: Human-readable job name
        priority: Job priority
        env: List of "KEY=VALUE" environment variables
        working_dir: Working directory for job

    Returns:
        Exit code (0 for success)

    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node
    """
    # Validate command
    if not command or len(command) == 0:
        click.echo("Error: Command cannot be empty")
        return 4

    # Parse environment variables
    env_vars = {}
    if env:
        for env_var in env:
            if '=' not in env_var:
                click.echo(f"Error: Invalid environment variable format: {env_var}")
                click.echo("Expected format: KEY=VALUE")
                return 2
            key, value = env_var.split('=', 1)
            env_vars[key] = value

    # Store command as script (first element) and script_args (remaining elements)
    # This maintains backward compatibility with the Job model
    script = command[0]
    script_args = command[1:] if len(command) > 1 else None

    # Use current directory if not specified (must be set on client side, not server side)
    if working_dir is None:
        working_dir = os.getcwd()

    try:
        # Connect to scheduler
        config = load_config()

        # Expand requirement shortcut if it exists
        original_req = req
        if req in config.client.req_shortcuts:
            req = config.client.req_shortcuts[req]
            click.echo(f"Using requirement shortcut '{original_req}' → {req}")

        # Expand ranges and sort for backward compatibility
        # This allows using new syntax (host:4-8, repeated hosts) without server changes
        expanded_req = expand_and_sort_requirements(req)
        if expanded_req != req:
            click.echo(f"Expanded requirement: {req} → {expanded_req}")
            req = expanded_req

        client = SchedulerClient(config=config)

        # Store original dependencies for comparison
        original_depends_on = list(depends_on) if depends_on else []

        # Submit job - use the full command as the display name
        command_str = ' '.join(command)
        click.echo(f"Submitting job: {command_str}")
        job = client.submit_job(
            script=script,
            requirements=req,
            name=name,
            script_args=script_args,
            working_dir=working_dir,
            env_vars=env_vars,
            dependencies=depends_on,
            priority=priority,
        )

        click.echo(f"\nJob submitted successfully!")
        click.echo(f"Job ID: {job.job_id}")
        click.echo(f"Status: {job.status.value}")
        click.echo(f"Requirements: {req}")

        # Show resolved dependencies
        if job.dependencies:
            dep_display = []
            for i, resolved_dep in enumerate(job.dependencies):
                if i < len(original_depends_on) and original_depends_on[i] != resolved_dep:
                    dep_display.append(f"{resolved_dep} (resolved)")
                else:
                    dep_display.append(resolved_dep)
            click.echo(f"Dependencies: {', '.join(dep_display)}")

        click.echo(f"\nView status: scheduler status (then press 'J' and search for job)")
        click.echo(f"View logs: scheduler logs {job.job_id}")
        return 0

    except ValidationException as e:
        click.echo(f"Validation error: {e}")
        return 2
    except ConnectionException as e:
        click.echo(f"❌ Connection error: {e}")
        return 3
    except Exception as e:
        click.echo(f"Error: {e}")
        return 1
