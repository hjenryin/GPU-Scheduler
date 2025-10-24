from typing import List

from scheduler.api import SchedulerClient
from scheduler.core import load_config, ConnectionException, JobNotFoundException


def cancel_command(job_ids: List[str]) -> int:
    """
    Cancel one or more jobs.

    Args:
        job_ids: List of job IDs to cancel

    Returns:
        Exit code (0 for success)

    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    try:
        config = load_config()
        client = SchedulerClient(config=config)

        for job_id in job_ids:
            try:
                client.cancel_job(job_id)
                print(f"Cancelled job: {job_id}")
            except JobNotFoundException:
                print(f"Job not found: {job_id}")

        return 0

    except ConnectionException as e:
        print(f"Connection error: {e}")
        return 3
    except Exception as e:
        print(f"Error: {e}")
        return 1
