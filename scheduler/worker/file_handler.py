from scheduler.core import Config
class FileHandler:
    """Handles script versioning and file operations"""

    def __init__(self, config: Config):
        """
        Initialize file handler.
        
        Args:
            config: Configuration instance
        """
        pass

    def create_versioned_copy(self, script_path: str, job_id: str) -> str:
        """
        Create a versioned copy of a script.
        
        Args:
            script_path: Original script path
            job_id: Job ID
            
        Returns:
            Path to versioned copy
            
        Raises:
            FileNotFoundError: If script doesn't exist
            PermissionDeniedException: If cannot create copy
        """
        pass

    def cleanup_versioned_files(self, max_age_hours: int = 24):
        """
        Clean up old versioned files.
        
        Args:
            max_age_hours: Maximum age of files to keep
        """
        pass

    def get_job_log_path(self, job_id: str, stderr: bool = False) -> str:
        """
        Get path to job log file.
        
        Args:
            job_id: Job ID
            stderr: If True, return stderr log path
            
        Returns:
            Path to log file
        """
        pass
