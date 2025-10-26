"""
Utilities for storing and retrieving head node connection information.
Head info is stored directly in worker lock files as JSON.
"""
import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def save_head_info(address: str):
    """
    Save head node address to worker lock file.
    Updates the lock file to include both PID and address in JSON format.
    
    Args:
        address: Head node address (host:port)
    """
    try:
        scheduler_dir = os.path.expanduser("~/.scheduler")
        if not os.path.exists(scheduler_dir):
            return
        
        # Find worker lock files and update them
        updated = False
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".lock"):
                lock_file = os.path.join(scheduler_dir, filename)
                
                try:
                    # Read existing lock file
                    with open(lock_file, 'r') as f:
                        data = json.load(f)
                    
                    pid = data.get('pid')
                    if not pid:
                        continue
                    
                    # Write updated format with both PID and address
                    data = {"pid": pid, "address": address}
                    with open(lock_file, 'w') as f:
                        json.dump(data, f)
                    
                    logger.info(f"Saved head node address to {filename}")
                    updated = True
                    break
                except Exception as e:
                    logger.warning(f"Failed to update lock file {filename}: {e}")
                    continue
        
        if not updated:
            logger.warning("No worker lock file found, cannot save head address")
    except Exception as e:
        logger.error(f"Failed to save head node address: {e}")


def load_head_info() -> Optional[str]:
    """
    Load head node address from worker lock files.
    Only returns address if the worker process is still running.
    
    Returns:
        Head node address, or None if not found or worker not active
    """
    try:
        scheduler_dir = os.path.expanduser("~/.scheduler")
        if not os.path.exists(scheduler_dir):
            return None
        
        # Look for worker lock files
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".lock"):
                lock_file = os.path.join(scheduler_dir, filename)
                
                try:
                    # Read lock file
                    with open(lock_file, 'r') as f:
                        data = json.load(f)
                    
                    pid = data.get('pid')
                    address = data.get('address')
                    
                    # Check if process is still running
                    if pid:
                        try:
                            os.kill(pid, 0)  # Check if process exists
                            if address:
                                logger.debug(f"Loaded head address from {filename} (PID: {pid})")
                                return address
                        except OSError:
                            # Process not running, skip this lock file
                            continue
                        
                except Exception:
                    continue
        
        return None
    except Exception as e:
        logger.error(f"Failed to load head node address: {e}")
        return None


def clear_head_info():
    """
    Clear all stored head node addresses.
    Note: This doesn't remove lock files, it just cleans up any .info files
    (for backwards compatibility if any exist).
    """
    try:
        scheduler_dir = os.path.expanduser("~/.scheduler")
        if not os.path.exists(scheduler_dir):
            return
        
        # Remove any worker info files (for backwards compatibility)
        for filename in os.listdir(scheduler_dir):
            if filename.startswith("worker-") and filename.endswith(".info"):
                try:
                    os.remove(os.path.join(scheduler_dir, filename))
                except Exception as e:
                    logger.warning(f"Failed to remove info file {filename}: {e}")
        
        logger.info("Cleared head node addresses")
    except Exception as e:
        logger.error(f"Failed to clear head node addresses: {e}")


