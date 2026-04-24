from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional, Dict, List
import yaml
import os

from scheduler.core.exceptions import ValidationException, PermissionDeniedException
from scheduler.core.utils import ensure_dir_exists
from scheduler.core.constants import (
    CONFIG_FILE_PATH,
    DEFAULT_PORT,
    DEFAULT_HEARTBEAT_TIMEOUT,
    DEFAULT_SCHEDULE_INTERVAL,
    DEFAULT_WORKER_PORT,
    DEFAULT_WORKER_DIR,
    DEFAULT_HEARTBEAT_INTERVAL,
    DEFAULT_GPU_POLL_INTERVAL,
    DEFAULT_GPU_UTIL_THRESHOLD,
    DEFAULT_GPU_MEM_THRESHOLD,
    DEFAULT_JOB_STARTUP_GRACE,
    DEFAULT_STORAGE_BACKEND,
    DEFAULT_DATA_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_CLIENT_REQ,
    DEFAULT_CONDA_COMMAND,
    TEMP_DIR_PATH,
    LOG_DIR_PATH,
    JOB_POLL_TIMEOUT as DEFAULT_JOB_POLL_TIMEOUT,
    DEFAULT_SNAPSHOT_MAX_FILE_SIZE,
    DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER,
    DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS,
    DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS,
    DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS
)


@dataclass(frozen=True)
class HeadConfig:
    port: int = 8266
    heartbeat_timeout: int = 30  # seconds
    scheduling_interval: int = 10  # seconds


@dataclass(frozen=True)
class WorkerConfig:
    """Worker node configuration"""
    temp_dir: str = TEMP_DIR_PATH
    log_dir: str = LOG_DIR_PATH
    work_dir: str = DEFAULT_WORKER_DIR
    port: int = DEFAULT_WORKER_PORT
    gpu_poll_interval: int = DEFAULT_GPU_POLL_INTERVAL
    gpu_util_threshold: float = DEFAULT_GPU_UTIL_THRESHOLD
    gpu_mem_threshold: float = DEFAULT_GPU_MEM_THRESHOLD
    job_startup_grace: int = DEFAULT_JOB_STARTUP_GRACE
    heartbeat_interval: int = DEFAULT_HEARTBEAT_INTERVAL
    job_poll_timeout: int = DEFAULT_JOB_POLL_TIMEOUT


@dataclass(frozen=True)
class StorageConfig:
    """Storage backend configuration"""
    backend: str = DEFAULT_STORAGE_BACKEND
    data_dir: str = DEFAULT_DATA_DIR
    db_path: str = DEFAULT_DB_PATH


@dataclass(frozen=True)
class ClientConfig:
    """Client defaults"""
    default_req: str = DEFAULT_CLIENT_REQ
    req_shortcuts: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CondaConfig:
    """Conda environment configuration"""
    command: str = DEFAULT_CONDA_COMMAND
    envs: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SnapshotConfig:
    """Git snapshot configuration"""
    max_file_size: int = DEFAULT_SNAPSHOT_MAX_FILE_SIZE
    max_files_per_folder: int = DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER
    data_type_limits: Dict[str, int] = field(default_factory=lambda: DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS.copy())
    always_include_extensions: List[str] = field(default_factory=lambda: list(DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS))
    exclude_patterns: List[str] = field(default_factory=lambda: list(DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS))


@dataclass(frozen=True)
class Config:
    """
    Main configuration container with nested sections.

    All configuration values are immutable after creation.
    Access configuration via nested attributes:
        - config.head.port
        - config.worker.gpu_poll_interval
        - config.storage.backend
    """
    address: Optional[str] = None
    head: HeadConfig = field(default_factory=HeadConfig)
    worker: WorkerConfig = field(default_factory=WorkerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    client: ClientConfig = field(default_factory=ClientConfig)
    conda: CondaConfig = field(default_factory=CondaConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)

    def __post_init__(self):
        """Validate configuration values after initialization."""
        pass

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'Config':
        """
        Create Config from dictionary with nested structure.

        Args:
            config_dict: Dictionary containing configuration values.
                        Can have nested dicts for 'head', 'worker', 'storage', 'client'

        Returns:
            Config instance

        Example:
            >>> config = Config.from_dict({
            ...     'address': 'localhost:8266',
            ...     'head': {'port': 9000},
            ...     'worker': {'gpu_poll_interval': 5}
            ... })
        """
        # Extract top-level address
        address = config_dict.get('address')

        # Extract and create nested configs
        head_dict = config_dict.get('head', config_dict.get('head_node', {}))
        worker_dict = config_dict.get('worker', config_dict.get('node', {}))
        storage_dict = config_dict.get('storage', {})
        client_dict = config_dict.get('client', {})
        conda_dict = config_dict.get('conda', {})
        snapshot_dict = config_dict.get('snapshot', {})

        # Filter to only valid fields for each sub-config
        def filter_dict(d: dict, dataclass_type):
            if not d:
                return {}
            valid_keys = {f.name for f in dataclass_type.__dataclass_fields__.values()}
            return {k: v for k, v in d.items() if k in valid_keys and v is not None}

        head_filtered = filter_dict(head_dict, HeadConfig)
        worker_filtered = filter_dict(worker_dict, WorkerConfig)
        storage_filtered = filter_dict(storage_dict, StorageConfig)
        client_filtered = filter_dict(client_dict, ClientConfig)
        conda_filtered = filter_dict(conda_dict, CondaConfig)
        snapshot_filtered = filter_dict(snapshot_dict, SnapshotConfig)

        return cls(
            address=address,
            head=HeadConfig(**head_filtered) if head_filtered else HeadConfig(),
            worker=WorkerConfig(**worker_filtered) if worker_filtered else WorkerConfig(),
            storage=StorageConfig(**storage_filtered) if storage_filtered else StorageConfig(),
            client=ClientConfig(**client_filtered) if client_filtered else ClientConfig(),
            conda=CondaConfig(**conda_filtered) if conda_filtered else CondaConfig(),
            snapshot=SnapshotConfig(**snapshot_filtered) if snapshot_filtered else SnapshotConfig()
        )

    def to_dict(self) -> dict:
        """
        Convert to dictionary with nested structure.

        Returns:
            Dictionary containing all configuration values

        Example:
            >>> config.to_dict()
            {
                'address': 'localhost:8266',
                'head': {'port': 8266, 'heartbeat_timeout': 60, ...},
                'worker': {...},
                'storage': {...},
                'client': {...},
                'conda': {...}
            }
        """
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
    # Use default path if not provided
    if config_path is None:
        config_path = os.path.expanduser(CONFIG_FILE_PATH)
    else:
        config_path = os.path.expanduser(config_path)

    # Check if file exists
    if not os.path.exists(config_path):
        # Return default config if file doesn't exist
        return Config()

    try:
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f) or {}
        return Config.from_dict(config_dict)
    except yaml.YAMLError as e:
        raise ValidationException(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ValidationException(f"Error loading config file: {e}")


def save_config(config: Config, config_path: Optional[str] = None):
    """
    Save configuration to YAML file.

    Args:
        config: Config instance to save
        config_path: Path to config file. If None, uses default path.

    Raises:
        PermissionDeniedException: If cannot write to config file
    """
    # Use default path if not provided
    if config_path is None:
        config_path = os.path.expanduser(CONFIG_FILE_PATH)
    else:
        config_path = os.path.expanduser(config_path)

    # Ensure parent directory exists
    parent_dir = os.path.dirname(config_path)
    if parent_dir:
        ensure_dir_exists(parent_dir)

    try:
        with open(config_path, 'w') as f:
            yaml.safe_dump(config.to_dict(), f, default_flow_style=False)
    except PermissionError as e:
        raise PermissionDeniedException(f"Cannot write to config file {config_path}: {e}")
    except Exception as e:
        raise PermissionDeniedException(f"Error writing config file: {e}")


def init_config(config_path: Optional[str] = None):
    """
    Initialize default configuration file.

    Args:
        config_path: Path to config file. If None, uses default path.

    Raises:
        FileExistsError: If config file already exists
        PermissionDeniedException: If cannot create config file
    """
    # Use default path if not provided
    if config_path is None:
        config_path = os.path.expanduser(CONFIG_FILE_PATH)
    else:
        config_path = os.path.expanduser(config_path)

    # Check if file already exists
    if os.path.exists(config_path):
        raise FileExistsError(f"Config file already exists: {config_path}")

    # Create default config and save it
    default_config = Config()
    save_config(default_config, config_path)
