# GPU Scheduler - Function Definitions

# Complete API specification for all modules

"""
=============================================================================

scheduler/core/models.py - Data Models
=============================================================================

"""

class JobStatus(Enum):
    """Job status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class NodeStatus(Enum):
    """Node status enumeration"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"

class GPUStats:
    """GPU statistics snapshot"""

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        temperature: int,
        power_draw: int,
        power_limit: int
    ):
        """
        Initialize GPU statistics.
        
        Args:
            gpu_id: GPU index (0-based)
            utilization: GPU utilization percentage (0-100)
            memory_used: Used GPU memory in bytes
            memory_total: Total GPU memory in bytes
            temperature: GPU temperature in Celsius
            power_draw: Current power draw in watts
            power_limit: Power limit in watts
        """
        pass
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all GPU stats
        """
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GPUStats':
        """Create GPUStats from dictionary.
        
        Args:
            data: Dictionary containing GPU stats
            
        Returns:
            GPUStats instance
        """
        pass
    
    def is_free(self, util_threshold: float, mem_threshold: float) -> bool:
        """Check if GPU is considered free based on thresholds.
        
        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage
            
        Returns:
            True if GPU is below both thresholds
        """
        pass

class GPU:
    """GPU resource representation"""

    def __init__(
        self,
        gpu_id: int,
        stats: GPUStats,
        assigned_job_id: Optional[str] = None,
        stable_since: Optional[datetime] = None
    ):
        """
        Initialize GPU.
        
        Args:
            gpu_id: GPU index
            stats: Current GPU statistics
            assigned_job_id: Job ID if GPU is assigned, None if free
            stable_since: Timestamp when GPU became stable (below threshold)
        """
        pass
    
    def update_stats(self, stats: GPUStats, util_threshold: float, mem_threshold: float):
        """Update GPU statistics and stability tracking.
        
        Args:
            stats: New GPU statistics
            util_threshold: Utilization threshold for stability
            mem_threshold: Memory threshold for stability
        """
        pass
    
    def is_stable(self, stable_time: int) -> bool:
        """Check if GPU has been stable for required duration.
        
        Args:
            stable_time: Required stable time in seconds
            
        Returns:
            True if GPU has been below threshold for stable_time seconds
        """
        pass
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing GPU data
        """
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'GPU':
        """Create GPU from dictionary.
        
        Args:
            data: Dictionary containing GPU data
            
        Returns:
            GPU instance
        """
        pass

class JobRequirement:
    """Job resource requirement specification"""

    def __init__(self, requirement_str: str):
        """
        Parse and initialize job requirement.
        
        Args:
            requirement_str: Requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")
            
        Raises:
            InvalidRequirementException: If requirement string is invalid
        """
        pass
    
    @property
    def alternatives(self) -> List[Tuple[Optional[str], int]]:
        """Get list of alternative requirements.
        
        Returns:
            List of (node_name, num_gpus) tuples. node_name is None for any node.
        """
        pass
    
    def matches_node(self, node_name: str, available_gpus: int) -> bool:
        """Check if a node satisfies this requirement.
        
        Args:
            node_name: Name of the node to check
            available_gpus: Number of available GPUs on the node
            
        Returns:
            True if node satisfies any alternative in the requirement
        """
        pass
    
    def __str__(self) -> str:
        """String representation of requirement.
        
        Returns:
            Human-readable requirement string
        """
        pass

class Job:
    """Job representation"""

    def __init__(
        self,
        job_id: str,
        name: str,
        script: str,
        requirements: JobRequirement,
        script_args: List[str] = None,
        working_dir: str = None,
        env_vars: Dict[str, str] = None,
        dependencies: List[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None,
        submitted_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        status: JobStatus = JobStatus.PENDING,
        assigned_node: Optional[str] = None,
        assigned_gpus: Optional[List[int]] = None,
        exit_code: Optional[int] = None,
        error_message: Optional[str] = None,
        versioned_script_path: Optional[str] = None
    ):
        """
        Initialize job.
        
        Args:
            job_id: Unique job identifier
            name: Human-readable job name
            script: Path to script to execute
            requirements: JobRequirement instance
            script_args: Arguments to pass to script
            working_dir: Working directory for execution
            env_vars: Environment variables
            dependencies: List of job IDs this job depends on
            priority: Job priority (higher = more important)
            timeout: Job timeout in seconds
            submitted_at: Submission timestamp
            started_at: Start timestamp
            completed_at: Completion timestamp
            status: Current job status
            assigned_node: Node name where job is assigned/running
            assigned_gpus: List of GPU IDs assigned to job
            exit_code: Process exit code
            error_message: Error message if failed
            versioned_script_path: Path to versioned script copy
        """
        pass
    
    def get_runtime(self) -> Optional[timedelta]:
        """Get job runtime duration.
        
        Returns:
            Runtime as timedelta if job started, None otherwise
        """
        pass
    
    def can_start(self, completed_job_ids: Set[str]) -> bool:
        """Check if all dependencies are satisfied.
        
        Args:
            completed_job_ids: Set of completed job IDs
            
        Returns:
            True if all dependencies are completed
        """
        pass
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all job data
        """
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Job':
        """Create Job from dictionary.
        
        Args:
            data: Dictionary containing job data
            
        Returns:
            Job instance
        """
        pass

class Node:
    """Worker node representation"""

    def __init__(
        self,
        node_name: str,
        address: str,
        num_gpus: int,
        gpus: List[GPU] = None,
        status: NodeStatus = NodeStatus.INITIALIZING,
        last_heartbeat: Optional[datetime] = None,
        registered_at: Optional[datetime] = None,
        grace_period_until: Optional[datetime] = None
    ):
        """
        Initialize node.
        
        Args:
            node_name: Unique node identifier
            address: Node IP address or hostname
            num_gpus: Number of GPUs on this node
            gpus: List of GPU instances
            status: Current node status
            last_heartbeat: Last heartbeat timestamp
            registered_at: Registration timestamp
            grace_period_until: Timestamp until which node is in grace period
        """
        pass
    
    def update_heartbeat(self, gpu_stats: List[GPUStats]):
        """Update node heartbeat and GPU statistics.
        
        Args:
            gpu_stats: List of GPU statistics from heartbeat
        """
        pass
    
    def get_free_gpus(self, util_threshold: float, mem_threshold: float, stable_time: int) -> List[int]:
        """Get list of free and stable GPU IDs.
        
        Args:
            util_threshold: Utilization threshold percentage
            mem_threshold: Memory usage threshold percentage
            stable_time: Required stable time in seconds
            
        Returns:
            List of GPU IDs that are free and stable
        """
        pass
    
    def is_in_grace_period(self) -> bool:
        """Check if node is currently in grace period.
        
        Returns:
            True if in grace period
        """
        pass
    
    def start_grace_period(self, duration: int):
        """Start a grace period for this node.
        
        Args:
            duration: Grace period duration in seconds
        """
        pass
    
    def assign_gpus(self, gpu_ids: List[int], job_id: str):
        """Assign GPUs to a job.
        
        Args:
            gpu_ids: List of GPU IDs to assign
            job_id: Job ID to assign GPUs to
        """
        pass
    
    def release_gpus(self, gpu_ids: List[int]):
        """Release GPUs from a job.
        
        Args:
            gpu_ids: List of GPU IDs to release
        """
        pass
    
    def to_dict(self) -> dict:
        """Convert to dictionary representation.
        
        Returns:
            Dictionary containing all node data
        """
        pass
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Node':
        """Create Node from dictionary.
        
        Args:
            data: Dictionary containing node data
            
        Returns:
            Node instance
        """
        pass

"""
=============================================================================

scheduler/core/config.py - Configuration Management
=============================================================================

"""

class Config:
    """Configuration container"""

    def __init__(self, config_dict: dict = None):
        """
        Initialize configuration from dictionary.
        
        Args:
            config_dict: Dictionary containing configuration values
        """
        pass
    
    # Properties for all configuration values
    @property
    def address(self) -> Optional[str]:
        """Head node address (host:port)"""
        pass
    
    @property
    def port(self) -> int:
        """Head node port"""
        pass
    
    @property
    def temp_dir(self) -> str:
        """Temporary directory path"""
        pass
    
    @property
    def log_dir(self) -> str:
        """Log directory path"""
        pass
    
    @property
    def heartbeat_timeout(self) -> int:
        """Heartbeat timeout in seconds"""
        pass
    
    @property
    def scheduling_interval(self) -> int:
        """Scheduling interval in seconds"""
        pass
    
    @property
    def gpu_poll_interval(self) -> int:
        """GPU polling interval in seconds"""
        pass
    
    @property
    def gpu_util_threshold(self) -> float:
        """GPU utilization threshold percentage"""
        pass
    
    @property
    def gpu_mem_threshold(self) -> float:
        """GPU memory threshold percentage"""
        pass
    
    @property
    def gpu_stable_time(self) -> int:
        """GPU stable time in seconds"""
        pass
    
    @property
    def job_startup_grace(self) -> int:
        """Job startup grace period in seconds"""
        pass
    
    def to_dict(self) -> dict:
        """Convert to dictionary.
        
        Returns:
            Dictionary containing all configuration values
        """
        pass

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

"""
=============================================================================

scheduler/core/utils.py - Utility Functions
=============================================================================

"""

def parse_requirements(req_str: str) -> List[Tuple[Optional[str], int]]:
    """
    Parse requirement string into list of alternatives.

    Args:
        req_str: Requirement string (e.g., "2", "gpu1:4", "gpu1:2,gpu2:4")
        
    Returns:
        List of (node_name, num_gpus) tuples. node_name is None for any node.
        
    Raises:
        InvalidRequirementException: If requirement string is invalid
    
    Examples:
        parse_requirements("2") -> [(None, 2)]
        parse_requirements("gpu1:4") -> [("gpu1", 4)]
        parse_requirements("gpu1:2,gpu2:4") -> [("gpu1", 2), ("gpu2", 4)]
    """
    pass

def format_duration(duration: timedelta) -> str:
    """
    Format duration as human-readable string.

    Args:
        duration: Duration to format
        
    Returns:
        Formatted string (e.g., "01:23:45", "5d 03:22:11")
    """
    pass

def format_timestamp(dt: datetime, relative: bool = False) -> str:
    """
    Format timestamp as human-readable string.

    Args:
        dt: Datetime to format
        relative: If True, return relative time (e.g., "2 hours ago")
        
    Returns:
        Formatted timestamp string
    """
    pass

def format_bytes(bytes_val: int) -> str:
    """
    Format bytes as human-readable string.

    Args:
        bytes_val: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB", "256 MB")
    """
    pass

def generate_job_id() -> str:
    """
    Generate unique job ID.

    Returns:
        Job ID string in format "job_<uuid>"
    """
    pass

def generate_versioned_filename(script_path: str, job_id: str) -> str:
    """
    Generate versioned filename for script.

    Args:
        script_path: Original script path
        job_id: Job ID
        
    Returns:
        Versioned filename (e.g., "script.py.scheduler_job_abc123_hash.py")
    """
    pass

def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """
    Check if a port is available for binding.

    Args:
        port: Port number to check
        host: Host address to bind to
        
    Returns:
        True if port is available
    """
    pass

def get_local_ip() -> str:
    """
    Get local IP address of this machine.

    Returns:
        IP address string
    """
    pass

def ensure_dir_exists(path: str):
    """
    Ensure directory exists, create if it doesn't.

    Args:
        path: Directory path
        
    Raises:
        PermissionDeniedException: If cannot create directory
    """
    pass

def parse_address(address: str) -> Tuple[str, int]:
    """
    Parse address string into host and port.

    Args:
        address: Address string (e.g., "host:port" or "host")
        
    Returns:
        Tuple of (host, port)
        
    Raises:
        ValidationException: If address format is invalid
    """
    pass

"""
=============================================================================

scheduler/core/exceptions.py - Custom Exceptions
=============================================================================

"""

class SchedulerException(Exception):
    """Base exception for scheduler errors"""
    pass

class NodeNotFoundException(SchedulerException):
    """Raised when node is not found"""
    pass

class JobNotFoundException(SchedulerException):
    """Raised when job is not found"""
    pass

class InvalidRequirementException(SchedulerException):
    """Raised when job requirement is invalid"""
    pass

class ConnectionException(SchedulerException):
    """Raised when connection to head node fails"""
    pass

class ValidationException(SchedulerException):
    """Raised when validation fails"""
    pass

class TimeoutException(SchedulerException):
    """Raised when operation times out"""
    pass

class PermissionDeniedException(SchedulerException):
    """Raised when permission is denied"""
    pass

"""
=============================================================================

scheduler/core/constants.py - System Constants
=============================================================================

"""

# Default values

DEFAULT_PORT = 8265
DEFAULT_HEARTBEAT_TIMEOUT = 60
DEFAULT_SCHEDULING_INTERVAL = 5
DEFAULT_GPU_POLL_INTERVAL = 10
DEFAULT_GPU_UTIL_THRESHOLD = 10.0
DEFAULT_GPU_MEM_THRESHOLD = 10.0
DEFAULT_GPU_STABLE_TIME = 30
DEFAULT_JOB_STARTUP_GRACE = 120

# API

API_VERSION = "v1"
API_BASE_PATH = f"/api/{API_VERSION}"

# Paths

CONFIG_FILE_PATH = "~/.scheduler/config.yaml"
TEMP_DIR_PATH = "~/.scheduler/tmp"
LOG_DIR_PATH = "~/.scheduler/logs"

# Job polling

JOB_POLL_TIMEOUT = 30  # Long-polling timeout in seconds

# Exit codes

EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_ARGUMENT_ERROR = 2
EXIT_CONNECTION_ERROR = 3
EXIT_NOT_FOUND_ERROR = 4
EXIT_PERMISSION_ERROR = 5
EXIT_TIMEOUT_ERROR = 6

"""
=============================================================================

scheduler/cli/main.py - Main CLI Entry Point
=============================================================================

"""

def main():
    """
    Main CLI entry point.

    This is the entry point registered in setup.py that gets called when
    the user runs 'scheduler' command. It parses the command and routes
    to the appropriate command handler.
    
    Returns:
        Exit code (0 for success, non-zero for errors)
    
    Example:
        $ scheduler start --head
        $ scheduler submit --req 2 train.py
        $ scheduler status
    """
    pass

"""
=============================================================================

scheduler/cli/main.py - CLI Entry Point
=============================================================================

"""

def main():
    """
    Main entry point for the scheduler CLI.

    This function:
    1. Sets up the argument parser with all subcommands
    2. Parses command-line arguments
    3. Dispatches to the appropriate command function
    4. Handles top-level exceptions and exit codes
    
    Returns:
        Exit code (0 for success, non-zero for errors)
        
    This is the function that setup.py entry_points will call.
    """
    pass

"""
=============================================================================

scheduler/cli/start.py - Start Command
=============================================================================

"""

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

"""
=============================================================================

scheduler/cli/stop.py - Stop Command
=============================================================================

"""

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

"""
=============================================================================

scheduler/cli/status.py - Status Command (TUI)
=============================================================================

"""

def status_command() -> int:
    """
    Launch interactive TUI for cluster monitoring.

    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
    """
    pass

"""
=============================================================================

scheduler/cli/submit.py - Submit Command
=============================================================================

"""

def submit_command(
    script: str,
    script_args: List[str] = None,
    req: str = "1",
    depends_on: List[str] = None,
    name: Optional[str] = None,
    priority: int = 0,
    env: List[str] = None,
    timeout: Optional[int] = None,
    working_dir: Optional[str] = None,
    async_submit: bool = False,
    log_to_driver: bool = False
) -> int:
    """
    Submit a new job to the scheduler.

    Args:
        script: Path to script to execute
        script_args: Arguments to pass to script
        req: Resource requirement string
        depends_on: List of job IDs to depend on
        name: Human-readable job name
        priority: Job priority
        env: List of "KEY=VALUE" environment variables
        timeout: Job timeout in seconds
        working_dir: Working directory for job
        async_submit: If True, return immediately after submission
        log_to_driver: If True, stream logs to stdout
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ValidationException: If arguments are invalid
        ConnectionException: If cannot connect to head node
        FileNotFoundError: If script doesn't exist
    """
    pass

"""
=============================================================================

scheduler/cli/jobs.py - Jobs Command
=============================================================================

"""

def jobs_command(
    job_ids: List[str] = None,
    format: str = "table",
    filter: str = "all",
    limit: int = 50
) -> int:
    """
    List jobs in non-interactive mode.

    Args:
        job_ids: Specific job IDs to query (None for all)
        format: Output format ("table", "json", "yaml")
        filter: Filter by status ("all", "pending", "running", "completed", "failed")
        limit: Maximum number of jobs to show
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If specified job not found
    """
    pass

"""
=============================================================================

scheduler/cli/logs.py - Logs Command
=============================================================================

"""

def logs_command(
    job_id: str,
    follow: bool = False,
    lines: int = 100,
    timestamps: bool = False,
    stderr: bool = False,
    both: bool = False
) -> int:
    """
    View logs for a specific job.

    Args:
        job_id: Job ID to view logs for
        follow: If True, follow logs in real-time
        lines: Number of lines to show from end
        timestamps: If True, show timestamps
        stderr: If True, show stderr instead of stdout
        both: If True, show both stdout and stderr
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    pass

"""
=============================================================================

scheduler/cli/cancel.py - Cancel Command
=============================================================================

"""

def cancel_command(job_ids: List[str], force: bool = False) -> int:
    """
    Cancel one or more jobs.

    Args:
        job_ids: List of job IDs to cancel
        force: If True, force kill without graceful shutdown
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
        JobNotFoundException: If job not found
    """
    pass

"""
=============================================================================

scheduler/cli/config.py - Config Command
=============================================================================

"""

def config_command(
    command: str,
    key: Optional[str] = None,
    value: Optional[str] = None,
    config_file: Optional[str] = None
) -> int:
    """
    Manage scheduler configuration.

    Args:
        command: Subcommand ("init", "show", "get", "set")
        key: Configuration key (for get/set)
        value: Configuration value (for set)
        config_file: Path to config file
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ValidationException: If arguments are invalid
        FileNotFoundError: If config file not found (for show/get)
    """
    pass

"""
=============================================================================

scheduler/head/orchestrator.py - Head Node Orchestrator
=============================================================================

"""

class Orchestrator:
    """Main head node orchestrator"""

    def __init__(self, config: Config):
        """
        Initialize orchestrator.
        
        Args:
            config: Configuration instance
        """
        pass
    
    def start(self):
        """
        Start the orchestrator and all components.
        
        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        pass
    
    def stop(self, graceful: bool = True):
        """
        Stop the orchestrator and all components.
        
        Args:
            graceful: If True, wait for jobs to complete
        """
        pass
    
    def run(self):
        """
        Run the orchestrator main loop (blocking).
        """
        pass
    
    def get_status(self) -> dict:
        """
        Get overall cluster status.
        
        Returns:
            Dictionary containing cluster status
        """
        pass

"""
=============================================================================

scheduler/head/scheduler.py - Job Scheduler
=============================================================================

"""

class Scheduler:
    """Job scheduling algorithm"""

    def __init__(
        self,
        job_manager: 'JobManager',
        node_manager: 'NodeManager',
        config: Config
    ):
        """
        Initialize scheduler.
        
        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        pass
    
    def schedule_cycle(self):
        """
        Run one scheduling cycle.
        Evaluates pending jobs and assigns to available nodes.
        """
        pass
    
    def try_schedule_job(self, job: Job) -> bool:
        """
        Try to schedule a single job.
        
        Args:
            job: Job to schedule
            
        Returns:
            True if job was successfully scheduled
        """
        pass
    
    def find_suitable_node(self, job: Job) -> Optional[Tuple[str, List[int]]]:
        """
        Find a suitable node for a job.
        
        Args:
            job: Job to find node for
            
        Returns:
            Tuple of (node_name, gpu_ids) if found, None otherwise
        """
        pass

"""
=============================================================================

scheduler/head/job_manager.py - Job Manager
=============================================================================

"""

class JobManager:
    """Manages job queue and lifecycle"""

    def __init__(self, persistence: 'PersistenceManager', config: Config):
        """
        Initialize job manager.
        
        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        pass
    
    def submit_job(
        self,
        script: str,
        requirements: str,
        name: Optional[str] = None,
        script_args: List[str] = None,
        working_dir: Optional[str] = None,
        env_vars: Dict[str, str] = None,
        dependencies: List[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None
    ) -> Job:
        """
        Submit a new job.
        
        Args:
            script: Path to script
            requirements: Requirement string
            name: Job name
            script_args: Script arguments
            working_dir: Working directory
            env_vars: Environment variables
            dependencies: Job dependencies
            priority: Job priority
            timeout: Job timeout
            
        Returns:
            Created Job instance
            
        Raises:
            ValidationException: If parameters are invalid
        """
        pass
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance if found, None otherwise
        """
        pass
    
    def list_jobs(
        self,
        status_filter: Optional[JobStatus] = None,
        limit: Optional[int] = None
    ) -> List[Job]:
        """
        List jobs with optional filtering.
        
        Args:
            status_filter: Filter by job status
            limit: Maximum number of jobs to return
            
        Returns:
            List of Job instances
        """
        pass
    
    def get_pending_jobs(self) -> List[Job]:
        """
        Get all pending jobs sorted by priority.
        
        Returns:
            List of pending Job instances
        """
        pass
    
    def get_running_jobs(self) -> List[Job]:
        """
        Get all running jobs.
        
        Returns:
            List of running Job instances
        """
        pass
    
    def get_completed_job_ids(self) -> Set[str]:
        """
        Get set of completed job IDs.
        
        Returns:
            Set of job IDs that are completed
        """
        pass
    
    def start_job(self, job_id: str, node_name: str, gpu_ids: List[int]):
        """
        Mark job as started.
        
        Args:
            job_id: Job ID
            node_name: Node where job is starting
            gpu_ids: GPUs assigned to job
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass
    
    def complete_job(self, job_id: str, exit_code: int):
        """
        Mark job as completed.
        
        Args:
            job_id: Job ID
            exit_code: Process exit code
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass
    
    def fail_job(self, job_id: str, error_message: str):
        """
        Mark job as failed.
        
        Args:
            job_id: Job ID
            error_message: Error message
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass
    
    def cancel_job(self, job_id: str):
        """
        Cancel a job.
        
        Args:
            job_id: Job ID
            
        Raises:
            JobNotFoundException: If job not found
        """
        pass

"""
=============================================================================

scheduler/head/node_manager.py - Node Manager
=============================================================================

"""

class NodeManager:
    """Manages worker node registry"""

    def __init__(self, persistence: 'PersistenceManager', config: Config):
        """
        Initialize node manager.
        
        Args:
            persistence: PersistenceManager instance
            config: Configuration instance
        """
        pass
    
    def register_node(
        self,
        node_name: str,
        address: str,
        num_gpus: int
    ) -> Node:
        """
        Register a new worker node.
        
        Args:
            node_name: Unique node name
            address: Node address
            num_gpus: Number of GPUs on node
            
        Returns:
            Created Node instance
            
        Raises:
            ValidationException: If node already exists
        """
        pass
    
    def update_heartbeat(
        self,
        node_name: str,
        gpu_stats: List[GPUStats]
    ):
        """
        Update node heartbeat and GPU statistics.
        
        Args:
            node_name: Node name
            gpu_stats: List of GPU statistics
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass
    
    def get_node(self, node_name: str) -> Optional[Node]:
        """
        Get node by name.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance if found, None otherwise
        """
        pass
    
    def list_nodes(self) -> List[Node]:
        """
        List all nodes.
        
        Returns:
            List of Node instances
        """
        pass
    
    def get_connected_nodes(self) -> List[Node]:
        """
        Get all connected nodes.
        
        Returns:
            List of connected Node instances
        """
        pass
    
    def check_timeouts(self):
        """
        Check for node heartbeat timeouts and mark as disconnected.
        """
        pass
    
    def start_node_grace_period(self, node_name: str):
        """
        Start grace period for a node.
        
        Args:
            node_name: Node name
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass
    
    def assign_gpus_to_job(
        self,
        node_name: str,
        gpu_ids: List[int],
        job_id: str
    ):
        """
        Assign GPUs to a job.
        
        Args:
            node_name: Node name
            gpu_ids: GPU IDs to assign
            job_id: Job ID
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass
    
    def release_gpus_from_job(
        self,
        node_name: str,
        gpu_ids: List[int]
    ):
        """
        Release GPUs from a job.
        
        Args:
            node_name: Node name
            gpu_ids: GPU IDs to release
            
        Raises:
            NodeNotFoundException: If node not found
        """
        pass

"""
=============================================================================

scheduler/head/api_server.py - HTTP API Server
=============================================================================

"""

class APIServer:
    """HTTP API server using FastAPI"""

    def __init__(
        self,
        job_manager: JobManager,
        node_manager: NodeManager,
        config: Config
    ):
        """
        Initialize API server.
        
        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        pass
    
    def start(self):
        """
        Start the API server.
        
        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        pass
    
    def stop(self):
        """
        Stop the API server.
        """
        pass
    
    def get_app(self) -> 'FastAPI':
        """
        Get FastAPI application instance.
        
        Returns:
            FastAPI app
        """
        pass

"""
=============================================================================

scheduler/head/persistence.py - Persistence Manager
=============================================================================

"""

class PersistenceManager:
    """Manages state persistence"""

    def __init__(self, backend: 'StorageBackend', config: Config):
        """
        Initialize persistence manager.
        
        Args:
            backend: StorageBackend instance
            config: Configuration instance
        """
        pass
    
    def save_job(self, job: Job):
        """
        Save job to storage.
        
        Args:
            job: Job to save
        """
        pass
    
    def load_job(self, job_id: str) -> Optional[Job]:
        """
        Load job from storage.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance if found, None otherwise
        """
        pass
    
    def load_all_jobs(self) -> List[Job]:
        """
        Load all jobs from storage.
        
        Returns:
            List of Job instances
        """
        pass
    
    def delete_job(self, job_id: str):
        """
        Delete job from storage.
        
        Args:
            job_id: Job ID
        """
        pass
    
    def save_node(self, node: Node):
        """
        Save node to storage.
        
        Args:
            node: Node to save
        """
        pass
    
    def load_node(self, node_name: str) -> Optional[Node]:
        """
        Load node from storage.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance if found, None otherwise
        """
        pass
    
    def load_all_nodes(self) -> List[Node]:
        """
        Load all nodes from storage.
        
        Returns:
            List of Node instances
        """
        pass
    
    def checkpoint(self):
        """
        Create a checkpoint of current state.
        """
        pass

"""
=============================================================================

scheduler/worker/daemon.py - Worker Daemon
=============================================================================

"""

class WorkerDaemon:
    """Main worker node daemon"""

    def __init__(self, config: Config, node_name: str, num_gpus: Optional[int] = None):
        """
        Initialize worker daemon.
        
        Args:
            config: Configuration instance
            node_name: Unique node name
            num_gpus: Number of GPUs (auto-detect if None)
        """
        pass
    
    def start(self):
        """
        Start the worker daemon and all components.
        
        Raises:
            ConnectionException: If cannot connect to head node
        """
        pass
    
    def stop(self, graceful: bool = True):
        """
        Stop the worker daemon and all components.
        
        Args:
            graceful: If True, wait for jobs to complete
        """
        pass
    
    def run(self):
        """
        Run the worker daemon main loop (blocking).
        """
        pass
    
    def register_with_head(self):
        """
        Register this worker with the head node.
        
        Raises:
            ConnectionException: If cannot connect to head node
        """
        pass

"""
=============================================================================

scheduler/worker/singleton.py - Singleton Daemon
=============================================================================

"""

class SingletonDaemon:
    """Ensures only one daemon runs per machine"""

    def __init__(self, lockfile_path: str):
        """
        Initialize singleton daemon.
        
        Args:
            lockfile_path: Path to lock file
        """
        pass
    
    def acquire_lock(self) -> bool:
        """
        Try to acquire singleton lock.
        
        Returns:
            True if lock acquired, False if another daemon is running
        """
        pass
    
    def release_lock(self):
        """
        Release singleton lock.
        """
        pass
    
    def __enter__(self):
        """Context manager entry."""
        pass
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass

def is_daemon_running(lockfile_path: str) -> bool:
    """
    Check if daemon is already running.

    Args:
        lockfile_path: Path to lock file
        
    Returns:
        True if daemon is running
    """
    pass

"""
=============================================================================

scheduler/worker/gpu_monitor.py - GPU Monitor
=============================================================================

"""

class GPUMonitor:
    """Monitors GPU status and statistics"""

    def __init__(self, config: Config):
        """
        Initialize GPU monitor.
        
        Args:
            config: Configuration instance
        """
        pass
    
    def detect_gpus(self) -> int:
        """
        Auto-detect number of GPUs on this machine.
        
        Returns:
            Number of GPUs detected
            
        Raises:
            RuntimeError: If nvidia-smi not available or fails
        """
        pass
    
    def poll_gpu_stats(self) -> List[GPUStats]:
        """
        Poll current GPU statistics.
        
        Returns:
            List of GPUStats for each GPU
            
        Raises:
            RuntimeError: If polling fails
        """
        pass
    
    def start_monitoring(self):
        """
        Start background GPU monitoring thread.
        """
        pass
    
    def stop_monitoring(self):
        """
        Stop background GPU monitoring thread.
        """
        pass
    
    def get_latest_stats(self) -> List[GPUStats]:
        """
        Get most recent GPU statistics.
        
        Returns:
            List of latest GPUStats
        """
        pass

"""
=============================================================================

scheduler/worker/job_executor.py - Job Executor
=============================================================================

"""

class JobExecutor:
    """Executes jobs as subprocesses"""

    def __init__(self, config: Config):
        """
        Initialize job executor.
        
        Args:
            config: Configuration instance
        """
        pass
    
    def execute_job(self, job: Job, gpu_ids: List[int]) -> int:
        """
        Execute a job.
        
        Args:
            job: Job to execute
            gpu_ids: GPU IDs assigned to this job
            
        Returns:
            Process ID of running job
            
        Raises:
            RuntimeError: If job execution fails
        """
        pass
    
    def get_job_status(self, pid: int) -> Tuple[bool, Optional[int]]:
        """
        Get status of a running job.
        
        Args:
            pid: Process ID
            
        Returns:
            Tuple of (is_running, exit_code). exit_code is None if still running.
        """
        pass
    
    def terminate_job(self, pid: int, force: bool = False):
        """
        Terminate a running job.
        
        Args:
            pid: Process ID
            force: If True, use SIGKILL instead of SIGTERM
        """
        pass
    
    def get_job_logs(
        self,
        job_id: str,
        lines: Optional[int] = None,
        stderr: bool = False
    ) -> str:
        """
        Get job logs.
        
        Args:
            job_id: Job ID
            lines: Number of lines from end (None for all)
            stderr: If True, return stderr instead of stdout
            
        Returns:
            Log contents as string
            
        Raises:
            JobNotFoundException: If job logs not found
        """
        pass

"""
=============================================================================

scheduler/worker/heartbeat.py - Heartbeat Sender
=============================================================================

"""

class HeartbeatSender:
    """Sends periodic heartbeat to head node"""

    def __init__(
        self,
        node_name: str,
        head_address: str,
        gpu_monitor: GPUMonitor,
        config: Config
    ):
        """
        Initialize heartbeat sender.
        
        Args:
            node_name: This node's name
            head_address: Head node address
            gpu_monitor: GPUMonitor instance
            config: Configuration instance
        """
        pass
    
    def start(self):
        """
        Start heartbeat thread.
        """
        pass
    
    def stop(self):
        """
        Stop heartbeat thread.
        """
        pass
    
    def send_heartbeat(self) -> bool:
        """
        Send a single heartbeat to head node.
        
        Returns:
            True if successful, False otherwise
        """
        pass
    
    def poll_for_job(self) -> Optional[Job]:
        """
        Long-poll head node for job assignment.
        
        Returns:
            Job if assigned, None if no job available
        """
        pass

"""
=============================================================================

scheduler/worker/file_handler.py - File Handler
=============================================================================

"""

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

"""
=============================================================================

scheduler/api/client.py - HTTP API Client
=============================================================================

"""

class SchedulerClient:
    """HTTP client for scheduler API"""

    def __init__(self, address: Optional[str] = None, config: Optional[Config] = None):
        """
        Initialize scheduler client.
        
        Args:
            address: Head node address (host:port). Auto-detect if None.
            config: Configuration instance (load default if None)
        """
        pass
    
    def submit_job(
        self,
        script: str,
        requirements: str,
        name: Optional[str] = None,
        script_args: List[str] = None,
        working_dir: Optional[str] = None,
        env_vars: Dict[str, str] = None,
        dependencies: List[str] = None,
        priority: int = 0,
        timeout: Optional[int] = None
    ) -> Job:
        """
        Submit a job.
        
        Args:
            (same as JobManager.submit_job)
            
        Returns:
            Created Job instance
            
        Raises:
            ConnectionException: If cannot connect to head node
            ValidationException: If parameters invalid
        """
        pass
    
    def get_job(self, job_id: str) -> Job:
        """
        Get job by ID.
        
        Args:
            job_id: Job ID
            
        Returns:
            Job instance
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass
    
    def list_jobs(
        self,
        status_filter: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Job]:
        """
        List jobs.
        
        Args:
            status_filter: Filter by status
            limit: Maximum number to return
            
        Returns:
            List of Job instances
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def cancel_job(self, job_id: str):
        """
        Cancel a job.
        
        Args:
            job_id: Job ID
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass
    
    def get_job_logs(
        self,
        job_id: str,
        lines: Optional[int] = None,
        stderr: bool = False
    ) -> str:
        """
        Get job logs.
        
        Args:
            job_id: Job ID
            lines: Number of lines from end
            stderr: If True, get stderr
            
        Returns:
            Log contents
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass
    
    def stream_job_logs(
        self,
        job_id: str,
        stderr: bool = False
    ) -> Iterator[str]:
        """
        Stream job logs in real-time.
        
        Args:
            job_id: Job ID
            stderr: If True, stream stderr
            
        Yields:
            Log lines as they arrive
            
        Raises:
            JobNotFoundException: If job not found
            ConnectionException: If cannot connect
        """
        pass
    
    def list_nodes(self) -> List[Node]:
        """
        List all nodes.
        
        Returns:
            List of Node instances
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def get_node(self, node_name: str) -> Node:
        """
        Get node by name.
        
        Args:
            node_name: Node name
            
        Returns:
            Node instance
            
        Raises:
            NodeNotFoundException: If node not found
            ConnectionException: If cannot connect
        """
        pass
    
    def register_node(
        self,
        node_name: str,
        address: str,
        num_gpus: int
    ) -> dict:
        """
        Register a worker node (worker use only).
        
        Args:
            node_name: Node name
            address: Node address
            num_gpus: Number of GPUs
            
        Returns:
            Registration response
            
        Raises:
            ValidationException: If parameters invalid
            ConnectionException: If cannot connect
        """
        pass
    
    def send_heartbeat(
        self,
        node_name: str,
        gpu_stats: List[GPUStats]
    ):
        """
        Send heartbeat (worker use only).
        
        Args:
            node_name: Node name
            gpu_stats: GPU statistics
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def poll_for_job(self, node_name: str, timeout: int = 30) -> Optional[Job]:
        """
        Long-poll for job assignment (worker use only).
        
        Args:
            node_name: Node name
            timeout: Poll timeout in seconds
            
        Returns:
            Job if assigned, None if timeout
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def report_job_complete(self, job_id: str, exit_code: int):
        """
        Report job completion (worker use only).
        
        Args:
            job_id: Job ID
            exit_code: Process exit code
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def report_job_failed(self, job_id: str, error_message: str):
        """
        Report job failure (worker use only).
        
        Args:
            job_id: Job ID
            error_message: Error message
            
        Raises:
            ConnectionException: If cannot connect
        """
        pass
    
    def health_check(self) -> bool:
        """
        Check if head node is healthy.
        
        Returns:
            True if healthy
        """
        pass

"""
=============================================================================

scheduler/api/routes.py - API Routes
=============================================================================

"""

def create_app(
    job_manager: JobManager,
    node_manager: NodeManager
) -> 'FastAPI':
    """
    Create FastAPI application with all routes.

    Args:
        job_manager: JobManager instance
        node_manager: NodeManager instance
        
    Returns:
        FastAPI application
    """
    pass

# Individual route handlers (used internally by create_app)

async def submit_job_route(request: 'JobSubmitRequest') -> 'JobResponse':
    """POST /api/v1/jobs - Submit a job"""
    pass

async def get_job_route(job_id: str) -> 'JobResponse':
    """GET /api/v1/jobs/{job_id} - Get job details"""
    pass

async def list_jobs_route(
    status: Optional[str] = None,
    limit: Optional[int] = None
) -> 'JobListResponse':
    """GET /api/v1/jobs - List jobs"""
    pass

async def cancel_job_route(job_id: str):
    """DELETE /api/v1/jobs/{job_id} - Cancel a job"""
    pass

async def get_job_logs_route(
    job_id: str,
    lines: Optional[int] = None,
    stderr: bool = False
) -> str:
    """GET /api/v1/jobs/{job_id}/logs - Get job logs"""
    pass

async def stream_job_logs_route(job_id: str, stderr: bool = False):
    """GET /api/v1/jobs/{job_id}/logs/stream - Stream job logs (WebSocket)"""
    pass

async def register_node_route(request: 'NodeRegisterRequest') -> dict:
    """POST /api/v1/nodes/register - Register a worker node"""
    pass

async def heartbeat_route(node_name: str, request: 'NodeHeartbeat'):
    """POST /api/v1/nodes/{node_name}/heartbeat - Send heartbeat"""
    pass

async def list_nodes_route() -> List['NodeResponse']:
    """GET /api/v1/nodes - List nodes"""
    pass

async def get_node_route(node_name: str) -> 'NodeResponse':
    """GET /api/v1/nodes/{node_name} - Get node details"""
    pass

async def poll_job_route(node_name: str) -> Optional['JobResponse']:
    """GET /api/v1/workers/{node_name}/jobs/next - Poll for job (long-polling)"""
    pass

async def complete_job_route(job_id: str, exit_code: int):
    """POST /api/v1/workers/jobs/{job_id}/complete - Mark job complete"""
    pass

async def fail_job_route(job_id: str, error_message: str):
    """POST /api/v1/workers/jobs/{job_id}/fail - Mark job failed"""
    pass

async def health_check_route() -> dict:
    """GET /api/v1/health - Health check"""
    pass

"""
=============================================================================

scheduler/api/schemas.py - Request/Response Schemas
=============================================================================

"""

class JobSubmitRequest(BaseModel):
    """Job submission request schema"""
    script: str
    requirements: str
    name: Optional[str] = None
    script_args: Optional[List[str]] = None
    working_dir: Optional[str] = None
    env_vars: Optional[Dict[str, str]] = None
    dependencies: Optional[List[str]] = None
    priority: int = 0
    timeout: Optional[int] = None

class JobResponse(BaseModel):
    """Job response schema"""
    job_id: str
    name: str
    script: str
    requirements: str
    status: str
    submitted_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_node: Optional[str] = None
    assigned_gpus: Optional[List[int]] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None

    @classmethod
    def from_job(cls, job: Job) -> 'JobResponse':
        """Create response from Job model"""
        pass

class JobListResponse(BaseModel):
    """Job list response schema"""
    jobs: List[JobResponse]
    total: int

class NodeRegisterRequest(BaseModel):
    """Node registration request schema"""
    node_name: str
    address: str
    num_gpus: int

class NodeHeartbeat(BaseModel):
    """Node heartbeat request schema"""
    gpu_stats: List[dict]  # List of GPUStats dicts

class GPUResponse(BaseModel):
    """GPU response schema"""
    gpu_id: int
    utilization: float
    memory_used: int
    memory_total: int
    temperature: int
    power_draw: int
    assigned_job_id: Optional[str] = None
    stable_since: Optional[str] = None

class NodeResponse(BaseModel):
    """Node response schema"""
    node_name: str
    address: str
    num_gpus: int
    status: str
    gpus: List[GPUResponse]
    last_heartbeat: Optional[str] = None
    registered_at: str

    @classmethod
    def from_node(cls, node: Node) -> 'NodeResponse':
        """Create response from Node model"""
        pass

"""
=============================================================================

scheduler/tui/app.py - TUI Application
=============================================================================

"""

# Note: Uses Textual framework

# from textual.app import App, ComposeResult

# from textual.widgets import Header, Footer, DataTable, Static, etc

class SchedulerTUI(App):
    """Main Textual TUI application"""

    # Textual App configuration
    TITLE = "GPU Scheduler"
    CSS_PATH = "styles.css"  # Optional CSS file for styling
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("n", "show_nodes", "Nodes"),
        ("j", "show_jobs", "Jobs"),
        ("g", "show_gpus", "GPUs"),
        ("h", "help", "Help"),
        ("/", "search", "Search"),
    ]
    
    def __init__(self, client: SchedulerClient):
        """
        Initialize TUI application.
        
        Args:
            client: SchedulerClient instance for API communication
        """
        super().__init__()
        self.client = client
        self.current_view = "cluster"  # cluster, nodes, jobs, gpus
        self.refresh_interval = 2  # seconds
        
    def compose(self) -> ComposeResult:
        """
        Compose the UI layout (Textual method).
        
        This is called by Textual to build the widget tree.
        Yields widgets that will be displayed.
        
        Yields:
            Textual widgets (Header, Footer, containers, etc.)
        """
        # Example structure:
        # yield Header()
        # yield ClusterView(id="cluster-view")
        # yield NodesView(id="nodes-view")
        # yield JobsView(id="jobs-view")
        # yield GPUsView(id="gpus-view")
        # yield Footer()
        pass
    
    def on_mount(self):
        """
        Called when app is mounted (Textual lifecycle method).
        
        Sets up:
        - Auto-refresh timer using set_interval
        - Initial data fetch
        - View visibility
        """
        pass
    
    def refresh_data(self):
        """
        Refresh data from head node.
        
        Fetches:
        - All jobs
        - All nodes
        - Updates all visible views
        
        Called by timer every refresh_interval seconds.
        """
        pass
    
    def action_quit(self):
        """
        Quit the application.
        
        Bound to 'q' key.
        """
        pass
    
    def action_show_nodes(self):
        """
        Switch to nodes view.
        
        Bound to 'n' key.
        """
        pass
    
    def action_show_jobs(self):
        """
        Switch to jobs view.
        
        Bound to 'j' key.
        """
        pass
    
    def action_show_gpus(self):
        """
        Switch to GPUs view.
        
        Bound to 'g' key.
        """
        pass
    
    def action_help(self):
        """
        Show help screen.
        
        Bound to 'h' key.
        """
        pass
    
    def action_search(self):
        """
        Show search/filter input.
        
        Bound to '/' key.
        """
        pass

def run_tui(client: SchedulerClient) -> int:
    """
    Run the TUI application.

    This is a convenience function that creates and runs the TUI.
    Used by the CLI status command.
    
    Args:
        client: SchedulerClient instance
        
    Returns:
        Exit code (0 for success)
        
    Raises:
        ConnectionException: If cannot connect to head node
    """
    pass

"""
=============================================================================

scheduler/tui/screens/cluster.py - Cluster Overview Screen
=============================================================================

"""

from textual.screen import Screen
from textual.app import ComposeResult

class ClusterScreen(Screen):
    """Cluster overview screen showing summary of nodes, GPUs, and jobs"""

    def compose(self) -> ComposeResult:
        """
        Compose the cluster overview layout.
        
        Yields:
            Widgets for cluster overview (stats, node table, GPU bars, job list)
        """
        pass
    
    def update_data(self, nodes: List[Node], jobs: List[Job]):
        """
        Update screen with new data.
        
        Args:
            nodes: List of Node instances
            jobs: List of Job instances
        """
        pass

"""
=============================================================================

scheduler/tui/screens/nodes.py - Nodes Detail Screen
=============================================================================

"""

class NodesScreen(Screen):
    """Detailed node information screen"""

    def compose(self) -> ComposeResult:
        """
        Compose the nodes detail layout.
        
        Yields:
            Widgets for node details (node selector, GPU table, job list)
        """
        pass
    
    def update_data(self, nodes: List[Node], jobs: List[Job]):
        """
        Update screen with new data.
        
        Args:
            nodes: List of Node instances
            jobs: List of Job instances
        """
        pass
    
    def on_node_selected(self, node_name: str):
        """
        Handle node selection.
        
        Args:
            node_name: Selected node name
        """
        pass

"""
=============================================================================

scheduler/tui/screens/jobs.py - Jobs List Screen
=============================================================================

"""

class JobsScreen(Screen):
    """Jobs list screen with filtering and sorting"""

    def compose(self) -> ComposeResult:
        """
        Compose the jobs list layout.
        
        Yields:
            Widgets for jobs list (filter controls, job table, details pane)
        """
        pass
    
    def update_data(self, jobs: List[Job]):
        """
        Update screen with new data.
        
        Args:
            jobs: List of Job instances
        """
        pass
    
    def on_job_selected(self, job_id: str):
        """
        Handle job selection.
        
        Args:
            job_id: Selected job ID
        """
        pass
    
    def filter_jobs(self, filter_text: str):
        """
        Filter jobs by search text.
        
        Args:
            filter_text: Text to filter by
        """
        pass

"""
=============================================================================

scheduler/tui/screens/gpus.py - GPUs Detail Screen
=============================================================================

"""

class GPUsScreen(Screen):
    """GPU details screen showing all GPUs across all nodes"""

    def compose(self) -> ComposeResult:
        """
        Compose the GPU details layout.
        
        Yields:
            Widgets for GPU details (GPU grid, stats tables)
        """
        pass
    
    def update_data(self, nodes: List[Node]):
        """
        Update screen with new data.
        
        Args:
            nodes: List of Node instances
        """
        pass

"""
=============================================================================

scheduler/tui/screens/job_detail.py - Job Detail Screen
=============================================================================

"""

class JobDetailScreen(Screen):
    """Single job detail screen"""

    def __init__(self, job_id: str):
        """
        Initialize job detail screen.
        
        Args:
            job_id: Job ID to display
        """
        super().__init__()
        self.job_id = job_id
    
    def compose(self) -> ComposeResult:
        """
        Compose the job detail layout.
        
        Yields:
            Widgets for job details (metadata, logs preview, actions)
        """
        pass
    
    def update_data(self, job: Job):
        """
        Update screen with new job data.
        
        Args:
            job: Job instance
        """
        pass
    
    def action_view_logs(self):
        """
        View full job logs.
        
        Bound to 'l' key.
        """
        pass
    
    def action_cancel_job(self):
        """
        Cancel the job.
        
        Bound to 'c' key.
        Shows confirmation dialog.
        """
        pass

"""
=============================================================================

scheduler/tui/widgets/gpu_bar.py - GPU Utilization Bar Widget
=============================================================================

"""

from textual.widgets import ProgressBar

class GPUBar(ProgressBar):
    """Custom progress bar widget for GPU utilization"""

    def __init__(
        self,
        gpu_id: int,
        utilization: float,
        memory_used: int,
        memory_total: int,
        **kwargs
    ):
        """
        Initialize GPU bar widget.
        
        Args:
            gpu_id: GPU ID
            utilization: Utilization percentage (0-100)
            memory_used: Used memory in bytes
            memory_total: Total memory in bytes
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self.gpu_id = gpu_id
        self.utilization = utilization
        self.memory_used = memory_used
        self.memory_total = memory_total
    
    def update_stats(
        self,
        utilization: float,
        memory_used: int,
        memory_total: int
    ):
        """
        Update GPU statistics.
        
        Args:
            utilization: New utilization percentage
            memory_used: New used memory
            memory_total: New total memory
        """
        pass
    
    def render(self) -> str:
        """
        Render the widget (Textual method).
        
        Returns:
            Renderable content for the widget
        """
        pass

"""
=============================================================================

scheduler/tui/widgets/node_table.py - Node Status Table Widget
=============================================================================

"""

from textual.widgets import DataTable

class NodeTable(DataTable):
    """Custom DataTable for displaying node information"""

    def __init__(self, **kwargs):
        """
        Initialize node table widget.
        
        Args:
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self._setup_columns()
    
    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Node, Status, GPUs, Free, Running, Last Heartbeat
        """
        pass
    
    def update_nodes(self, nodes: List[Node]):
        """
        Update table with node data.
        
        Args:
            nodes: List of Node instances
        """
        pass
    
    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (node name)
        """
        pass

"""
=============================================================================

scheduler/tui/widgets/job_table.py - Job List Table Widget
=============================================================================

"""

class JobTable(DataTable):
    """Custom DataTable for displaying job information"""

    def __init__(self, **kwargs):
        """
        Initialize job table widget.
        
        Args:
            **kwargs: Additional widget arguments
        """
        super().__init__(**kwargs)
        self._setup_columns()
    
    def _setup_columns(self):
        """
        Set up table columns.
        
        Columns: Job ID, Name, Status, Node, GPUs, Runtime
        """
        pass
    
    def update_jobs(self, jobs: List[Job]):
        """
        Update table with job data.
        
        Args:
            jobs: List of Job instances
        """
        pass
    
    def filter_by_status(self, status: Optional[JobStatus] = None):
        """
        Filter jobs by status.
        
        Args:
            status: JobStatus to filter by (None for all)
        """
        pass
    
    def on_row_selected(self, row_key: str):
        """
        Handle row selection.
        
        Args:
            row_key: Selected row key (job ID)
        """
        pass

"""
=============================================================================

scheduler/tui/utils.py - TUI Utilities
=============================================================================

"""

def format_gpu_memory(bytes_val: int) -> str:
    """
    Format GPU memory for display.

    Args:
        bytes_val: Memory in bytes
        
    Returns:
        Formatted string (e.g., "12.5 GB")
    """
    pass

def get_status_color(status: str) -> str:
    """
    Get color for a status string.

    Args:
        status: Status string (e.g., "running", "failed")
        
    Returns:
        Textual color name (e.g., "green", "red")
    """
    pass

def format_runtime(runtime: Optional[timedelta]) -> str:
    """
    Format runtime for display.

    Args:
        runtime: Runtime duration
        
    Returns:
        Formatted string (e.g., "01:23:45" or "-")
    """
    pass

def create_gpu_utilization_bar(utilization: float, width: int = 20) -> str:
    """
    Create ASCII bar for GPU utilization.

    Args:
        utilization: Utilization percentage (0-100)
        width: Bar width in characters
        
    Returns:
        ASCII bar string (e.g., "████████░░ 82%")
    """
    pass

def wrap_in_api_client(func):
    """
    Decorator to handle API client exceptions in TUI.

    Catches ConnectionException and other API errors,
    displays error message to user, and handles gracefully.
    
    Args:
        func: Function to wrap
        
    Returns:
        Wrapped function
    """
    pass

"""
=============================================================================

scheduler/storage/backend.py - Storage Backend Interface
=============================================================================

"""

class StorageBackend(ABC):
    """Abstract base class for storage backends"""

    @abstractmethod
    def save_job(self, job: Job):
        """Save job to storage"""
        pass
    
    @abstractmethod
    def load_job(self, job_id: str) -> Optional[Job]:
        """Load job from storage"""
        pass
    
    @abstractmethod
    def load_all_jobs(self) -> List[Job]:
        """Load all jobs from storage"""
        pass
    
    @abstractmethod
    def delete_job(self, job_id: str):
        """Delete job from storage"""
        pass
    
    @abstractmethod
    def save_node(self, node: Node):
        """Save node to storage"""
        pass
    
    @abstractmethod
    def load_node(self, node_name: str) -> Optional[Node]:
        """Load node from storage"""
        pass
    
    @abstractmethod
    def load_all_nodes(self) -> List[Node]:
        """Load all nodes from storage"""
        pass
    
    @abstractmethod
    def close(self):
        """Close storage backend and cleanup resources"""
        pass

"""
=============================================================================

scheduler/storage/sqlite_backend.py - SQLite Backend
=============================================================================

"""

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

"""
=============================================================================

scheduler/storage/file_backend.py - File-based Backend
=============================================================================

"""

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
