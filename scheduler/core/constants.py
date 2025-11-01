
# Default values

# Head node defaults
DEFAULT_PORT = 8265
DEFAULT_HEARTBEAT_TIMEOUT = 60
DEFAULT_SCHEDULE_INTERVAL = 5  # Note: renamed from SCHEDULING_INTERVAL for consistency

# Worker node defaults
DEFAULT_WORKER_PORT = 8266
DEFAULT_WORKER_DIR = "~/.scheduler/work"
DEFAULT_HEARTBEAT_INTERVAL = 10
DEFAULT_GPU_POLL_INTERVAL = 10
DEFAULT_GPU_UTIL_THRESHOLD = 10.0
DEFAULT_GPU_MEM_THRESHOLD = 10.0
DEFAULT_GPU_STABLE_TIME = 30
DEFAULT_JOB_STARTUP_GRACE = 120

# Storage defaults
DEFAULT_STORAGE_BACKEND = "file"
DEFAULT_DATA_DIR = "~/.scheduler/data"
DEFAULT_DB_PATH = "~/.scheduler/scheduler.db"

# Client defaults
DEFAULT_CLIENT_REQ = "1"

# Legacy alias for backward compatibility in tests
DEFAULT_SCHEDULING_INTERVAL = DEFAULT_SCHEDULE_INTERVAL

# API

API_VERSION = "v1"
API_BASE_PATH = f"/api/{API_VERSION}"

# Paths

CONFIG_FILE_PATH = "~/.scheduler/config.yaml"
TEMP_DIR_PATH = "~/.scheduler/tmp"
LOG_DIR_PATH = "~/.scheduler/logs"

# Job polling

JOB_POLL_TIMEOUT = 30  # Long-polling timeout in seconds

# Git snapshot defaults
#
# These can be overridden by setting attributes on the Config object:
#
# Example usage in code:
#   config.snapshot_max_file_size = 2 * 1024 * 1024  # 2 MB
#   config.snapshot_max_files_per_folder = 500
#   config.snapshot_data_type_limits = {'.pkl': 10 * 1024 * 1024}
#   config.snapshot_always_include_extensions = {'.py', '.yaml', '.txt'}
#   config.snapshot_exclude_patterns = {'__pycache__', '*.pyc'}
#
# Or via configuration file (~/.scheduler/config.yaml):
#   snapshot_max_file_size: 2097152  # 2 MB in bytes
#   snapshot_max_files_per_folder: 500
#   snapshot_data_type_limits:
#     .pkl: 10485760  # 10 MB in bytes
#   snapshot_always_include_extensions: ['.py', '.yaml', '.txt']
#   snapshot_exclude_patterns: ['__pycache__', '*.pyc']

DEFAULT_SNAPSHOT_MAX_FILE_SIZE = 512 * 1024  # 512 KB
DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER = 1000  # Maximum files in a single folder

# Data type-specific size limits (in bytes) - override DEFAULT_SNAPSHOT_MAX_FILE_SIZE
DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS = {
    '.json': 1 * 1024 * 1024,  # JSON files: 1 MB
    '.csv': 1 * 1024 * 1024,   # CSV files: 1 MB
}

# File extensions that should always be included in snapshots
DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS = {
    '.py', '.sh', '.yaml', '.yml', '.json', '.txt', '.md',
    '.toml', '.ini', '.cfg', '.conf', '.env'
}

# Patterns to always exclude from snapshots
DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS = {
    '__pycache__', '.pytest_cache', '.mypy_cache', '.tox',
    '.egg-info', '.eggs', 'build', 'dist', '.git', '.scheduler-git',
    '*.pyc', '*.pyo', '*.pyd', '.so', '*.dylib',
    '.coverage', 'htmlcov', '.DS_Store', '*.swp', '*.swo',
    '.vscode', '.idea', '*.log'
}

# Exit codes

EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_ARGUMENT_ERROR = 2
EXIT_CONNECTION_ERROR = 3
EXIT_NOT_FOUND_ERROR = 4
EXIT_PERMISSION_ERROR = 5
EXIT_TIMEOUT_ERROR = 6
