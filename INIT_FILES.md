# GPU Scheduler - __init__.py Files

# This document defines what each __init__.py file should expose

"""
=============================================================================

scheduler/__init__.py - Main Package Entry Point
=============================================================================

"""

# Version information

__version__ = "0.1.0"

# Expose core models for easy imports

from scheduler.core.models import (
    Job,
    Node,
    GPU,
    JobRequirement,
    JobStatus,
    NodeStatus,
)

# Expose core exceptions

from scheduler.core.exceptions import (
    SchedulerException,
    NodeNotFoundException,
    JobNotFoundException,
    InvalidRequirementException,
    ConnectionException,
    ValidationException,
)

# Expose configuration

from scheduler.core.config import Config, load_config

# Expose API client for external use

from scheduler.api.client import SchedulerClient

__all__ = [
    # Version
    "__version__",
    # Models
    "Job",
    "Node",
    "GPU",
    "JobRequirement",
    "JobStatus",
    "NodeStatus",
    # Exceptions
    "SchedulerException",
    "NodeNotFoundException",
    "JobNotFoundException",
    "InvalidRequirementException",
    "ConnectionException",
    "ValidationException",
    # Config
    "Config",
    "load_config",
    # Client
    "SchedulerClient",
]

"""
=============================================================================

scheduler/cli/__init__.py - Command-Line Interface Entry Point
=============================================================================

"""

from scheduler.cli.start import start_command
from scheduler.cli.stop import stop_command
from scheduler.cli.status import status_command
from scheduler.cli.submit import submit_command
from scheduler.cli.jobs import jobs_command
from scheduler.cli.logs import logs_command
from scheduler.cli.cancel import cancel_command
from scheduler.cli.config import config_command

# Main CLI entry point function

from scheduler.cli.main import main

__all__ = [
    "main",
    "start_command",
    "stop_command",
    "status_command",
    "submit_command",
    "jobs_command",
    "logs_command",
    "cancel_command",
    "config_command",
]

"""
=============================================================================

scheduler/core/__init__.py - Core Shared Functionality
=============================================================================

"""

from scheduler.core.models import (
    Job,
    Node,
    GPU,
    JobRequirement,
    JobStatus,
    NodeStatus,
    GPUStats,
)

from scheduler.core.config import Config, load_config, save_config

from scheduler.core.exceptions import (
    SchedulerException,
    NodeNotFoundException,
    JobNotFoundException,
    InvalidRequirementException,
    ConnectionException,
    ValidationException,
    TimeoutException,
    PermissionDeniedException,
)

from scheduler.core.utils import (
    parse_requirements,
    format_duration,
    format_timestamp,
    format_bytes,
    generate_job_id,
    generate_versioned_filename,
    is_port_available,
    get_local_ip,
)

from scheduler.core.constants import (
    DEFAULT_PORT,
    DEFAULT_HEARTBEAT_TIMEOUT,
    DEFAULT_SCHEDULING_INTERVAL,
    DEFAULT_GPU_POLL_INTERVAL,
    DEFAULT_GPU_UTIL_THRESHOLD,
    DEFAULT_GPU_MEM_THRESHOLD,
    DEFAULT_GPU_STABLE_TIME,
    DEFAULT_JOB_STARTUP_GRACE,
    API_VERSION,
    CONFIG_FILE_PATH,
    TEMP_DIR_PATH,
    LOG_DIR_PATH,
)

__all__ = [
    # Models
    "Job",
    "Node",
    "GPU",
    "JobRequirement",
    "JobStatus",
    "NodeStatus",
    "GPUStats",
    # Config
    "Config",
    "load_config",
    "save_config",
    # Exceptions
    "SchedulerException",
    "NodeNotFoundException",
    "JobNotFoundException",
    "InvalidRequirementException",
    "ConnectionException",
    "ValidationException",
    "TimeoutException",
    "PermissionDeniedException",
    # Utils
    "parse_requirements",
    "format_duration",
    "format_timestamp",
    "format_bytes",
    "generate_job_id",
    "generate_versioned_filename",
    "is_port_available",
    "get_local_ip",
    # Constants
    "DEFAULT_PORT",
    "DEFAULT_HEARTBEAT_TIMEOUT",
    "DEFAULT_SCHEDULING_INTERVAL",
    "DEFAULT_GPU_POLL_INTERVAL",
    "DEFAULT_GPU_UTIL_THRESHOLD",
    "DEFAULT_GPU_MEM_THRESHOLD",
    "DEFAULT_GPU_STABLE_TIME",
    "DEFAULT_JOB_STARTUP_GRACE",
    "API_VERSION",
    "CONFIG_FILE_PATH",
    "TEMP_DIR_PATH",
    "LOG_DIR_PATH",
]

"""
=============================================================================

scheduler/head/__init__.py - Head Node Components
=============================================================================

"""

from scheduler.head.orchestrator import Orchestrator
from scheduler.head.scheduler import Scheduler
from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.head.api_server import APIServer
from scheduler.head.persistence import PersistenceManager

__all__ = [
    "Orchestrator",
    "Scheduler",
    "JobManager",
    "NodeManager",
    "APIServer",
    "PersistenceManager",
]

"""
=============================================================================

scheduler/worker/__init__.py - Worker Node Components
=============================================================================

"""

from scheduler.worker.daemon import WorkerDaemon
from scheduler.worker.singleton import SingletonDaemon, is_daemon_running
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.worker.job_executor import JobExecutor
from scheduler.worker.heartbeat import HeartbeatSender
from scheduler.worker.file_handler import FileHandler

__all__ = [
    "WorkerDaemon",
    "SingletonDaemon",
    "is_daemon_running",
    "GPUMonitor",
    "JobExecutor",
    "HeartbeatSender",
    "FileHandler",
]

"""
=============================================================================

scheduler/api/__init__.py - HTTP API Layer
=============================================================================

"""

from scheduler.api.client import SchedulerClient
from scheduler.api.routes import create_app
from scheduler.api.schemas import (
    JobSubmitRequest,
    JobResponse,
    NodeRegisterRequest,
    NodeHeartbeat,
    NodeResponse,
    JobListResponse,
)

__all__ = [
    "SchedulerClient",
    "create_app",
    "JobSubmitRequest",
    "JobResponse",
    "NodeRegisterRequest",
    "NodeHeartbeat",
    "NodeResponse",
    "JobListResponse",
]

"""
=============================================================================

scheduler/tui/__init__.py - Terminal User Interface
=============================================================================

"""

from scheduler.tui.app import SchedulerTUI

__all__ = [
    "SchedulerTUI",
]

"""
=============================================================================

scheduler/storage/__init__.py - Data Persistence
=============================================================================

"""

from scheduler.storage.backend import StorageBackend
from scheduler.storage.sqlite_backend import SQLiteBackend
from scheduler.storage.file_backend import FileBackend

__all__ = [
    "StorageBackend",
    "SQLiteBackend",
    "FileBackend",
]
