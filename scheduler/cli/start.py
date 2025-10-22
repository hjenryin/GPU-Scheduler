from typing import Iterator, List, Optional
from scheduler.core.constants import DEFAULT_PORT
def start_command(
    head: bool = False,
    address: Optional[str] = None,
    port: int = DEFAULT_PORT,
    node_name: Optional[str] = None,
    num_gpus: Optional[int] = None,
    temp_dir: Optional[str] = None,
    log_dir: Optional[str] = None,
    block: bool = True,
    log_level: str = "INFO",
    **kwargs
) -> int:
    """
    Start scheduler as head node or worker node.

    Args:
        head: If True, start as head node
        address: Head node address (for worker nodes)
        port: Port for head node
        node_name: Name for this node
        num_gpus: Number of GPUs (auto-detect if None)
        temp_dir: Temporary directory path
        log_dir: Log directory path
        block: If True, block until stopped
        log_level: Logging level
        **kwargs: Additional head/worker specific options
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node (worker)
        PermissionDeniedException: If cannot bind to port (head)
    """
    pass
