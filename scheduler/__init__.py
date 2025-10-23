
# Version information

__version__ = "0.1.0"

# Expose public APIs from submodules
# Each import uses the submodule's __init__.py to maintain proper boundaries

from scheduler.core import (
    Job,
    Node,
    GPU,
    JobRequirement,
    JobStatus,
    NodeStatus,
    SchedulerException,
    NodeNotFoundException,
    JobNotFoundException,
    InvalidRequirementException,
    ConnectionException,
    ValidationException,
    Config,
    load_config,
)

from scheduler.api import SchedulerClient

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
