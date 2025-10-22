def stop_command(force: bool = False, all_nodes: bool = False) -> int:
    """
    Stop scheduler on current node or all nodes.

    Args:
        force: If True, force kill without graceful shutdown
        all_nodes: If True, stop all nodes in cluster (head only)
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to scheduler
    """
    pass
