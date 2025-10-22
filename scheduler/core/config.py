from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Config:
    """Configuration container"""

    # Head node configuration
    address: Optional[str] = None  # Head node address (host:port)
    port: int = 8265  # Head node port

    # Directory paths
    temp_dir: str = "/tmp/scheduler"  # Temporary directory path
    log_dir: str = "/var/log/scheduler"  # Log directory path

    # Timing configuration
    heartbeat_timeout: int = 30  # Heartbeat timeout in seconds
    scheduling_interval: int = 10  # Scheduling interval in seconds

    # GPU monitoring configuration
    gpu_poll_interval: int = 5  # GPU polling interval in seconds
    gpu_util_threshold: float = 10.0  # GPU utilization threshold percentage
    gpu_mem_threshold: float = 10.0  # GPU memory threshold percentage
    gpu_stable_time: int = 60  # GPU stable time in seconds

    # Job configuration
    job_startup_grace: int = 30  # Job startup grace period in seconds

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'Config':
        """
        Create Config from dictionary.

        Args:
            config_dict: Dictionary containing configuration values

        Returns:
            Config instance
        """
        # Only use keys that are valid Config fields
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered_dict = {k: v for k, v in config_dict.items() if k in valid_keys}
        return cls(**filtered_dict)

    def to_dict(self) -> dict:
        """Convert to dictionary.

        Returns:
            Dictionary containing all configuration values
        """
        from dataclasses import asdict
        return asdict(self)


def load_config(config_path: Optional[str] = None) -> Config:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file. If None, uses default path.
        
    Returns:
        Config instance with loaded values
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValidationException: If config file is invalid
    """
    pass


def save_config(config: Config, config_path: Optional[str] = None):
    """
    Save configuration to YAML file.

    Args:
        config: Config instance to save
        config_path: Path to config file. If None, uses default path.
        
    Raises:
        PermissionDeniedException: If cannot write to config file
    """
    pass


def init_config(config_path: Optional[str] = None):
    """
    Initialize default configuration file.

    Args:
        config_path: Path to config file. If None, uses default path.
        
    Raises:
        FileExistsError: If config file already exists
        PermissionDeniedException: If cannot create config file
    """
    pass
