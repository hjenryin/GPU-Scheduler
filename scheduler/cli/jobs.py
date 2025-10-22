from typing import Iterator, List, Optional

def jobs_command(
    job_ids: List[str] = None,
    format: str = "table",
    filter: str = "all",
    limit: int = 50
) -> int:
    """
    List jobs in non-interactive mode.

    Args:
        job_ids: Specific job IDs to query (None for all)
        format: Output format ("table", "json", "yaml")
        filter: Filter by status ("all", "pending", "running", "completed", "failed")
        limit: Maximum number of jobs to show
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If specified job not found
    """
    pass
