from scheduler.storage.backend import StorageBackend
class SQLiteBackend(StorageBackend):
    """SQLite storage backend"""

    def __init__(self, db_path: str):
        """
        Initialize SQLite backend.
        
        Args:
            db_path: Path to SQLite database file
        """
        pass

    def _init_schema(self):
        """
        Initialize database schema.
        Creates tables if they don't exist.
        """
        pass

    # Implement all StorageBackend abstract methods
    # (same signatures as in backend.py)
