from typing import Iterator, List, Optional


def cancel_command(job_ids: List[str], force: bool = False) -> int:
    """
    Cancel one or more jobs.

    Args:
        job_ids: List of job IDs to cancel
        force: If True, force kill without graceful shutdown
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    pass
