from scheduler.storage.backend import StorageBackend
class FileBackend(StorageBackend):
    """File-based storage backend (JSON)"""

    def __init__(self, storage_dir: str):
        """
        Initialize file backend.
        
        Args:
            storage_dir: Directory for storage files
        """
        pass

    # Implement all StorageBackend abstract methods
    # (same signatures as in backend.py)
