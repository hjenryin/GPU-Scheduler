# GPU Scheduler - Codebase Structure

This document outlines the organization of the codebase, explaining the purpose of each file and directory.

---

## Architecture Overview

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                         Head Node                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │ Orchestrator│  │  Scheduler │  │   API Server       │    │
│  │            │  │            │  │   (FastAPI)        │    │
│  └────────────┘  └────────────┘  └────────────────────┘    │
│  ┌────────────┐  ┌────────────┐                             │
│  │ Job Manager│  │Node Manager│                             │
│  └────────────┘  └────────────┘                             │
└─────────────────────────────────────────────────────────────┘
                           ↕ HTTP
┌─────────────────────────────────────────────────────────────┐
│                      Worker Nodes                            │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │   Daemon   │  │GPU Monitor │  │  Job Executor      │    │
│  │            │  │            │  │                    │    │
│  └────────────┘  └────────────┘  └────────────────────┘    │
│  ┌────────────┐  ┌────────────┐                             │
│  │ Heartbeat  │  │File Handler│                             │
│  └────────────┘  └────────────┘                             │
└─────────────────────────────────────────────────────────────┘
                           ↕ HTTP
┌─────────────────────────────────────────────────────────────┐
│                      CLI / TUI                               │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────┐    │
│  │  Commands  │  │ API Client │  │   Interactive      │    │
│  │            │  │            │  │   TUI (status)     │    │
│  └────────────┘  └────────────┘  └────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Core:**

- Python 3.8+
- FastAPI (API server framework)
- uvicorn (ASGI server)
- requests (HTTP client)
- pydantic (data validation)

**TUI:**

- textual OR rich (terminal UI framework)
- Choose textual for better structure or rich for simpler rendering

**GPU Monitoring:**

- pynvml (NVIDIA Management Library Python bindings)

**CLI:**

- Recommend click for wider adoption

**Configuration:**

- pyyaml (YAML parsing)

**Storage:**

- SQLite (production)
- JSON/Pickle (development/testing)

**Testing:**

- pytest
- pytest-asyncio (for async tests)
- pytest-cov (coverage)

---

## Directory Overview

```
gpu-scheduler/
├── scheduler/              # Main Python package
│   ├── __init__.py
│   ├── cli/               # Command-line interface
│   ├── head/              # Head node (orchestrator) components
│   ├── worker/            # Worker node (daemon) components
│   ├── core/              # Shared core functionality
│   ├── api/               # HTTP API client/server
│   ├── tui/               # Terminal user interface
│   └── storage/           # Data persistence layer
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── docs/                  # Documentation
├── setup.py              # Package installation
├── requirements.txt      # Python dependencies
├── README.md            # User-facing readme
└── .gitignore
```

---

## 1. `scheduler/` - Main Package

The core package containing all scheduler functionality.

### 1.1 `scheduler/cli/` - Command-Line Interface

Implements all user-facing CLI commands. Each command is a separate module.

```
cli/
├── __init__.py           # CLI entry point, command router
├── start.py              # `scheduler start` - Start head/worker node
├── stop.py               # `scheduler stop` - Stop scheduler
├── status.py             # `scheduler status` - Interactive TUI
├── submit.py             # `scheduler submit` - Submit jobs
├── jobs.py               # `scheduler jobs` - List/query jobs
├── logs.py               # `scheduler logs` - View job logs
├── cancel.py             # `scheduler cancel` - Cancel jobs
└── config.py             # `scheduler config` - Configuration management
```

**Purpose of each file:**

- **`__init__.py`**:
  - Main CLI entry point using Click or argparse
  - Routes commands to appropriate handlers
  - Common CLI utilities (output formatting, error handling)

- **`start.py`**:
  - Parses `scheduler start` arguments
  - Determines if starting as head or worker
  - Initializes and launches appropriate component
  - Handles singleton daemon logic (check if already running)

- **`stop.py`**:
  - Gracefully stops scheduler processes
  - Sends shutdown signals
  - Cleans up resources

- **`status.py`**:
  - Entry point for the interactive TUI
  - Connects to head node
  - Launches the TUI application (delegates to `tui/app.py`)

- **`submit.py`**:
  - Parses job submission arguments
  - Validates resource requirements
  - Creates versioned script copies
  - Submits job to head node via API

- **`jobs.py`**:
  - Lists jobs in non-interactive mode
  - Filters and formats job data
  - Outputs in various formats (table, json, yaml)

- **`logs.py`**:
  - Streams job logs from head node
  - Supports following logs in real-time
  - Handles stdout/stderr selection

- **`cancel.py`**:
  - Cancels one or more jobs
  - Sends cancellation requests to head node
  - Handles force termination

- **`config.py`**:
  - Manages configuration file
  - Init, show, get, set commands
  - Validates configuration values

---

### 1.2 `scheduler/head/` - Head Node Components

Implements the central orchestrator that manages the cluster.

```
head/
├── __init__.py
├── orchestrator.py       # Main orchestrator class
├── scheduler.py          # Job scheduling algorithm
├── job_manager.py        # Job queue and lifecycle management
├── node_manager.py       # Node registry and health monitoring
├── api_server.py         # HTTP API server (FastAPI/Flask)
└── persistence.py        # State persistence and recovery
```

**Purpose of each file:**

- **`orchestrator.py`**:
  - Main entry point for head node
  - Coordinates all head node components
  - Manages startup/shutdown lifecycle
  - Runs scheduling loop
  - Handles signal handling (SIGTERM, SIGINT)

- **`scheduler.py`**:
  - Core scheduling algorithm
  - Evaluates pending jobs against available resources
  - Matches jobs to nodes based on requirements
  - Handles job dependencies (DAG resolution)
  - Implements priority-based scheduling
  - Respects grace periods and stability windows

- **`job_manager.py`**:
  - Manages job queue (pending, running, completed, failed)
  - Job state transitions
  - Job creation, validation, and storage
  - Dependency tracking
  - Job history and cleanup
  - Generates job IDs

- **`node_manager.py`**:
  - Maintains registry of all worker nodes
  - Processes heartbeat messages
  - Tracks node health and connectivity
  - Monitors GPU availability per node
  - Detects disconnected nodes (heartbeat timeout)
  - Manages node grace periods

- **`api_server.py`**:
  - HTTP API server implementation (FastAPI recommended)
  - Defines all API routes
  - Handles authentication if needed
  - Serves API for workers and clients
  - WebSocket support for log streaming

- **`persistence.py`**:
  - Persists state to disk
  - Saves job queue, node registry
  - Recovers state on restart
  - Handles database/file operations
  - Implements periodic checkpointing

---

### 1.3 `scheduler/worker/` - Worker Node Components

Implements the daemon that runs on GPU machines.

```
worker/
├── __init__.py
├── daemon.py             # Main worker daemon
├── singleton.py          # Singleton daemon implementation
├── gpu_monitor.py        # GPU monitoring and stability detection
├── job_executor.py       # Job execution and process management
├── heartbeat.py          # Heartbeat sender to head node
└── file_handler.py       # Script versioning and caching
```

**Purpose of each file:**

- **`daemon.py`**:
  - Main entry point for worker node
  - Coordinates all worker components
  - Manages lifecycle (startup, run loop, shutdown)
  - Handles reconnection to head node
  - Signal handling

- **`singleton.py`**:
  - Implements singleton pattern
  - Checks if daemon already running on machine
  - If running, forwards commands to existing daemon
  - If not, becomes the daemon
  - Uses local socket/port binding

- **`gpu_monitor.py`**:
  - Polls GPU stats using nvidia-smi or pynvml
  - Tracks utilization, memory, temperature, power
  - Implements stability detection (consecutive checks)
  - Determines which GPUs are "free"
  - Respects gpu_stable_time configuration
  - Detects new processes on GPUs

- **`job_executor.py`**:
  - Executes jobs as subprocesses
  - Sets CUDA_VISIBLE_DEVICES
  - Captures stdout/stderr to log files
  - Monitors job status (running, completed, failed)
  - Handles job termination (graceful and forced)
  - Reports job status to head node
  - Implements job startup grace period

- **`heartbeat.py`**:
  - Sends periodic heartbeat to head node
  - Includes GPU stats in heartbeat
  - Polls for new job assignments
  - Handles connection failures and retries
  - Long-polling implementation for job assignments

- **`file_handler.py`**:
  - Creates versioned copies of scripts
  - Generates unique filenames (job_id + hash)
  - Manages cleanup of old versioned files
  - Handles script validation

---

### 1.4 `scheduler/core/` - Shared Core Functionality

Common code used by both head and worker nodes.

```
core/
├── __init__.py
├── models.py             # Data models and classes
├── config.py             # Configuration loading and validation
├── utils.py              # Utility functions
├── constants.py          # System constants
├── exceptions.py         # Custom exceptions
└── logging_config.py     # Logging configuration
```

**Purpose of each file:**

- **`models.py`**:
  - Defines data classes for Job, Node, GPU, etc.
  - Serialization/deserialization methods
  - Validation logic
  - Data class definitions:
    - `Job`: id, name, script, requirements, status, etc.
    - `Node`: name, address, gpus, status, etc.
    - `GPU`: id, utilization, memory, temperature, etc.
    - `JobRequirement`: parsed from --req string
    - `JobStatus`: enum (pending, running, completed, failed)

- **`config.py`**:
  - Loads configuration from YAML file
  - Environment variable overrides
  - Default values
  - Configuration validation
  - Config class with all settings
  - Path resolution (~/.scheduler expansion)

- **`utils.py`**:
  - Common utility functions
  - Time formatting
  - String parsing (parse --req format)
  - File operations
  - Process management helpers
  - Network utilities

- **`constants.py`**:
  - System-wide constants
  - Default values (ports, timeouts, intervals)
  - API endpoints
  - File paths
  - Status codes

- **`exceptions.py`**:
  - Custom exception classes
  - SchedulerException (base)
  - NodeNotFoundException
  - JobNotFoundException
  - InvalidRequirementException
  - ConnectionException
  - etc.

- **`logging_config.py`**:
  - Centralized logging configuration
  - Log format definitions
  - File and console handlers
  - Log level management
  - Per-component loggers

---

### 1.5 `scheduler/api/` - HTTP API Layer

Client and server components for HTTP communication.

```
api/
├── __init__.py
├── client.py             # HTTP client for CLI/worker
├── routes.py             # API route definitions
├── schemas.py            # Request/response schemas (Pydantic)
└── middleware.py         # API middleware (logging, auth, etc.)
```

**Purpose of each file:**

- **`client.py`**:
  - HTTP client used by CLI commands
  - HTTP client used by worker daemon
  - Methods for all API endpoints
  - Connection pooling
  - Retry logic
  - Error handling
  - Auto-discovery of head node address

- **`routes.py`**:
  - FastAPI route definitions
  - Endpoint implementations
  - Job routes: POST /jobs, GET /jobs, etc.
  - Node routes: POST /nodes/register, etc.
  - Worker routes: GET /workers/{node}/jobs/next
  - Health check endpoint
  - Long-polling for job assignments

- **`schemas.py`**:
  - Pydantic models for API requests/responses
  - JobSubmitRequest, JobResponse
  - NodeRegisterRequest, NodeHeartbeat
  - Validation logic
  - Serialization helpers

- **`middleware.py`**:
  - Request logging
  - Error handling
  - Rate limiting (if needed)
  - CORS headers
  - Authentication (future)

---

### 1.6 `scheduler/tui/` - Terminal User Interface

Interactive TUI for monitoring (like nvitop).

```
tui/
├── __init__.py
├── app.py                # Main TUI application (Textual App)
├── screens/              # Different screens (Textual screens)
│   ├── __init__.py
│   ├── cluster.py        # Cluster overview screen
│   ├── nodes.py          # Detailed node screen
│   ├── jobs.py           # Jobs list screen
│   ├── gpus.py           # GPU details screen
│   └── job_detail.py     # Single job details screen
├── widgets/              # Custom Textual widgets
│   ├── __init__.py
│   ├── gpu_bar.py        # GPU utilization bar widget
│   ├── node_table.py     # Node status table widget
│   └── job_table.py      # Job list table widget
└── utils.py              # TUI utilities
```

**Purpose of each file:**

- **`app.py`**:
  - Main Textual App class
  - Keyboard binding definitions (q, n, j, g, etc.)
  - Screen management and switching
  - Auto-refresh timer (2s interval using set_interval)
  - Data fetching from head node API
  - Global state management

- **`screens/cluster.py`**:
  - Default cluster overview screen (Textual Screen)
  - Composes: Header, node table (DataTable), GPU bars, job list
  - Shows nodes, GPUs, jobs summary
  - Keyboard bindings for switching views
  - Reactive data updates

- **`screens/nodes.py`**:
  - Detailed node screen (press 'N')
  - Composes: Header, node selector, per-GPU stats table
  - Shows selected node's GPU statistics
  - Running jobs on node
  - Node health information

- **`screens/jobs.py`**:
  - Full jobs list screen (press 'J')
  - Composes: Header, jobs DataTable with filtering
  - Built-in Textual filtering and sorting
  - Search functionality using Textual Input widget
  - Job selection handling

- **`screens/gpus.py`**:
  - Detailed GPU screen (press 'G')
  - Composes: Grid layout of GPU cards
  - All GPUs across all nodes
  - Per-GPU statistics with progress bars
  - Stability indicators (time free)

- **`screens/job_detail.py`**:
  - Single job details screen (press Enter on job)
  - Composes: Vertical layout with labeled sections
  - Job metadata display
  - Dependencies list
  - Environment variables
  - Action buttons (view logs, cancel, retry)

- **`widgets/gpu_bar.py`**:
  - Custom Textual Widget for GPU utilization
  - Inherits from Textual ProgressBar or Static
  - Color coding (low/medium/high)
  - Shows percentage and GPU ID

- **`widgets/node_table.py`**:
  - Custom DataTable subclass
  - Pre-configured columns for node data
  - Sorting and selection logic
  - Color coding for status

- **`widgets/job_table.py`**:
  - Custom DataTable subclass
  - Pre-configured columns for job data
  - Status icons/colors
  - Selection handling

- **`utils.py`**:
  - Data formatting helpers (bytes to human-readable, etc.)
  - Color scheme definitions
  - API client wrapper for TUI
  - Error handling utilities

---

### 1.7 `scheduler/storage/` - Data Persistence

Handles state persistence and recovery.

```
storage/
├── __init__.py
├── backend.py            # Storage backend interface
├── sqlite_backend.py     # SQLite implementation
└── file_backend.py       # File-based storage (JSON/pickle)
```

**Purpose of each file:**

- **`backend.py`**:
  - Abstract base class for storage backends
  - Defines interface for CRUD operations
  - Methods: save_job, load_jobs, save_node, etc.

- **`sqlite_backend.py`**:
  - SQLite database implementation
  - Job table, node table
  - Efficient queries
  - Transaction management
  - Good for production use
  - Note: For initial development, recreating the DB on schema changes is fine

- **`file_backend.py`**:
  - Simple file-based storage
  - JSON or pickle format
  - Good for development/testing
  - Easy to inspect state
  - Recommended for initial development

---

## 2. `tests/` - Test Suite

Comprehensive test coverage for all components.

```
tests/
├── __init__.py
├── conftest.py           # Pytest fixtures
├── unit/                 # Unit tests
│   ├── test_models.py
│   ├── test_scheduler.py
│   ├── test_gpu_monitor.py
│   └── ...
├── integration/          # Integration tests
│   ├── test_head_worker.py
│   ├── test_job_lifecycle.py
│   └── ...
└── e2e/                  # End-to-end tests
    └── test_full_workflow.py
```

**Test categories:**

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test interactions between components
- **E2E tests**: Test complete workflows from CLI to execution

---

## 3. `scripts/` - Utility Scripts

Helper scripts for development and deployment.

```
scripts/
├── install.sh            # Installation script
├── setup_dev.sh          # Development environment setup
├── start_cluster.sh      # Start a test cluster locally
├── cleanup.sh            # Clean up test files
└── benchmark.sh          # Performance benchmarking
```

---

## 4. `docs/` - Documentation

Additional documentation beyond the main README.

```
docs/
├── API_REFERENCE.md      # User-facing API documentation
├── DEVELOPMENT.md        # Developer guide
├── ARCHITECTURE.md       # Architecture overview
├── CONTRIBUTING.md       # Contribution guidelines
└── examples/             # Example scripts and configs
    ├── simple_job.py
    ├── pipeline.sh
    └── config.yaml
```

---

## 5. Root Files

- **`setup.py`**:
  - Package installation configuration
  - Entry points for CLI commands
  - Dependencies
  - Package metadata

- **`requirements.txt`**:
  - Python dependencies
  - Required libraries:
    - **FastAPI** (API server) - Modern, fast ASGI framework
    - **uvicorn** (ASGI server) - Production-ready server
    - **requests** (HTTP client) - Simple HTTP requests
    - **pydantic** (data validation) - Type-safe data models
    - **pyyaml** (config parsing) - YAML configuration files
    - **textual** (TUI framework) - Interactive terminal UI ⭐
    - **click** (CLI framework) - Command-line interface
    - **pynvml** (GPU monitoring) - NVIDIA Management Library bindings
    - **psutil** (process info) - Cross-platform process utilities
  - Optional dependencies:
    - **pytest** (testing) - For development
    - **black** (formatting) - Code formatting
    - **ruff** (linting) - Fast Python linter

- **`README.md`**:
  - User-facing documentation
  - Quick start guide
  - Installation instructions
  - Basic usage examples
  - Link to full documentation

- **`.gitignore`**:
  - Python artifacts (**pycache**, *.pyc)
  - Virtual environments
  - IDE files
  - Log files
  - Local config files

---

## Component Interactions

### Job Submission Flow

```
CLI (submit.py)
    ↓ (HTTP POST /api/v1/jobs)
Head API Server (routes.py)
    ↓ (validates and creates job)
Job Manager (job_manager.py)
    ↓ (adds to queue)
Scheduler (scheduler.py)
    ↓ (evaluates pending jobs)
    ↓ (finds available node)
Worker Daemon (heartbeat.py long-polls /api/v1/workers/{node}/jobs/next)
    ↓ (receives job assignment)
Job Executor (job_executor.py)
    ↓ (creates versioned script, sets CUDA_VISIBLE_DEVICES)
    ↓ (executes as subprocess)
    ↓ (streams logs, monitors status)
    ↓ (POST /api/v1/workers/jobs/{job_id}/complete)
Head Node (job_manager.py)
    ↓ (marks job complete)
```

### GPU Monitoring Flow

```
Worker (gpu_monitor.py)
    ↓ (polls nvidia-smi every 10s)
GPU Stats (util, memory, temp, power)
    ↓ (accumulated in daemon)
Heartbeat (heartbeat.py)
    ↓ (POST /api/v1/nodes/{node}/heartbeat with GPU stats)
Head Node (node_manager.py)
    ↓ (updates node state)
    ↓ (tracks GPU stability timers)
Scheduler (scheduler.py)
    ↓ (uses GPU availability in scheduling decisions)
```

### TUI Update Flow

```
TUI App (app.py)
    ↓ (every 2s refresh)
    ↓ (GET /api/v1/nodes, GET /api/v1/jobs)
Head API Server (routes.py)
    ↓ (queries job manager + node manager)
Job Manager + Node Manager
    ↓ (returns current state)
TUI Views (cluster_view.py, jobs_view.py, etc.)
    ↓ (renders updated data)
User sees real-time status
```

### Node Registration Flow

```
Worker Daemon (daemon.py startup)
    ↓ (detects GPUs via nvidia-smi)
    ↓ (POST /api/v1/nodes/register)
Head Node (node_manager.py)
    ↓ (registers node in registry)
    ↓ (responds with node_id confirmation)
Worker Daemon
    ↓ (starts heartbeat thread)
    ↓ (starts GPU monitoring thread)
    ↓ (starts job polling loop)
```

---

## Design Constraints & Important Notes

### GPU Scheduling Limitations

1. **CUDA_VISIBLE_DEVICES Compliance**:
   - The scheduler sets CUDA_VISIBLE_DEVICES for each job
   - However, not all frameworks/libraries respect this variable
   - Some code may attempt to use all visible GPUs regardless
   - The scheduler **cannot** enforce GPU isolation at the system level
   - Users should verify their code respects GPU assignments

2. **Grace Period Necessity**:
   - When a job starts, the node enters a grace period (default 120s)
   - No new jobs scheduled during this time
   - Prevents: race conditions, initialization conflicts, data loading gaps
   - Tunable via `--job-startup-grace`

3. **Stability Detection**:
   - A GPU is only "free" after staying below threshold for consecutive checks
   - Default: 30 seconds of stable low utilization
   - Prevents: false positives during brief idle periods
   - Tunable via `--gpu-stable-time`

4. **Shared Machine Environment**:
   - System is designed for shared GPU clusters
   - Other users may start jobs outside the scheduler
   - The scheduler monitors but cannot prevent external GPU usage
   - Grace periods help detect external jobs

### Communication Protocol

- **HTTP-based**: No SSH required between machines
- **Long-polling**: Workers poll for job assignments (no push needed)
- **Stateless API**: Workers can reconnect after disconnection
- **Heartbeat timeout**: 60s default, configurable

### File Versioning Strategy

- Scripts are copied with versioned names: `script.py.scheduler_{job_id}_{hash}.py`
- Original script can be modified after submission
- Versioned copy is immutable
- Executed script uses versioned copy
- Cleanup after job completion (keep for N hours for debugging)

---

## Component Interactions

---

## Adding New Features

### Adding a New CLI Command

1. Create `scheduler/cli/new_command.py`
2. Implement command logic
3. Register in `scheduler/cli/__init__.py`
4. Add tests in `tests/unit/test_cli.py`
5. Update API_REFERENCE.md

### Adding a New API Endpoint

1. Define schema in `scheduler/api/schemas.py`
2. Add route in `scheduler/api/routes.py`
3. Update client methods in `scheduler/api/client.py`
4. Add tests
5. Update documentation

### Adding a New TUI View

1. Create view in `scheduler/tui/views/`
2. Register in `scheduler/tui/app.py`
3. Add keyboard shortcut
4. Update help screen
5. Test rendering

---

## Development Workflow

### Setting Up Development Environment

```bash
# Clone repository
git clone <repo-url>
cd gpu-scheduler

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in development mode
pip install -e .
pip install -r requirements-dev.txt

# Run tests
pytest

# Start local cluster for testing
./scripts/start_cluster.sh
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=scheduler --cov-report=html

# Specific test
pytest tests/unit/test_scheduler.py::test_job_scheduling
```

### Code Style

- Follow PEP 8
- Use type hints
- Use docstrings (Google style)
- Format with black
- Lint with ruff or flake8

---

## Design Principles

1. **Modularity**: Each component has a single responsibility
2. **Testability**: Components are designed for easy testing
3. **Extensibility**: Easy to add new features without modifying core
4. **Configuration**: Behavior controlled through config, not code changes
5. **Error Handling**: Graceful degradation and clear error messages
6. **Logging**: Comprehensive logging for debugging
7. **Documentation**: Code is self-documenting with clear naming

---

## Next Steps

1. Implement core models (`models.py`)
2. Build CLI framework (`cli/__init__.py`)
3. Implement head node orchestrator
4. Implement worker daemon
5. Build API layer
6. Create TUI
7. Write tests
8. Documentation
9. Packaging and distribution

---

*This structure provides a solid foundation for building and maintaining the GPU scheduler system.*
