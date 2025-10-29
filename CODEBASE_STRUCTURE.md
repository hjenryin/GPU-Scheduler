# GPU Scheduler - Codebase Structure

This document outlines the organization of the codebase, explaining the purpose of each file and directory.

**Current Status:** ✅ **Production-Ready** - All core features implemented and tested with 88% code coverage.

**Last Updated:** December 2024

---

## Quick Overview

The GPU Scheduler is a distributed job scheduling system for GPU clusters with the following key features:

- **Distributed Architecture:** Head node orchestrates multiple worker nodes
- **HTTP-based Communication:** No SSH required between machines
- **GPU Monitoring:** Real-time GPU utilization tracking via nvidia-smi/pynvml
- **Smart Scheduling:** Priority-based scheduling with dependency support
- **Interactive TUI:** Real-time cluster monitoring interface (like nvitop)
- **CLI Interface:** Complete command-line interface for all operations
- **Persistence:** Dual backend support (SQLite for production, file-based for development)
- **Job Versioning:** Automatic script versioning for reproducibility
- **Comprehensive Testing:** 865 tests with 88% coverage

**Technology Stack:**
- Python 3.10+
- FastAPI + uvicorn (API server)
- Textual (TUI framework)
- Click (CLI framework)
- pynvml (GPU monitoring)
- SQLite/JSON (persistence)

**Project Metrics:**
- **Lines of Code:** ~3,500 (production code)
- **Test Code:** ~6,000 lines
- **Total Tests:** 865 (100% pass rate)
- **Code Coverage:** 88%
- **Components:** 7 major subsystems
- **Supported Platforms:** Linux, macOS, Windows (with NVIDIA GPUs)

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
├── __init__.py           # CLI package initialization
├── main.py               # CLI entry point using Click
├── start.py              # `scheduler start` - Start head/worker node
├── stop.py               # `scheduler stop` - Stop scheduler
├── status.py             # `scheduler status` - Interactive TUI
├── submit.py             # `scheduler submit` - Submit jobs
├── jobs.py               # `scheduler jobs` - List/query jobs
├── logs.py               # `scheduler logs` - View job logs
├── cancel.py             # `scheduler cancel` - Cancel jobs
├── config.py             # `scheduler config` - Configuration management
└── helpers.py            # CLI helper utilities
```

**Purpose of each file:**

- **`main.py`**:
  - Main CLI entry point using Click framework
  - Defines all command decorators and routing
  - Routes commands to appropriate handler modules
  - Common CLI utilities (error handling, exit codes)
  - Handles KeyboardInterrupt and exception handling

- **`helpers.py`**:
  - CLI helper functions
  - `check_head_address_or_prompt()` - Validates head node connection
  - Provides user-friendly error messages for connection issues

- **`start.py`**:
  - Implements `start_command()` function
  - Parses `scheduler start` arguments
  - Determines if starting as head or worker
  - Initializes and launches appropriate component
  - Handles singleton daemon logic (check if already running)
  - Manages worker thread lifecycle

- **`stop.py`**:
  - Implements `stop_command()` function
  - Gracefully stops scheduler processes via SIGTERM
  - Cleans up lock files and resources
  - Supports stopping individual workers or all nodes

- **`status.py`**:
  - Implements `status_command()` function
  - Entry point for the interactive TUI
  - Connects to head node via API client
  - Launches the TUI application (delegates to `tui/app.py`)

- **`submit.py`**:
  - Implements `submit_command()` function
  - Parses job submission arguments
  - Validates resource requirements and script existence
  - Creates versioned script copies
  - Submits job to head node via API
  - Supports async and sync submission modes

- **`jobs.py`**:
  - Implements `jobs_command()` function
  - Lists jobs in non-interactive mode
  - Filters and formats job data
  - Outputs in various formats (table, json, yaml)

- **`logs.py`**:
  - Implements `logs_command()` function
  - Retrieves job logs from head node
  - Supports following logs in real-time
  - Handles stdout/stderr selection
  - Supports showing both streams and timestamps

- **`cancel.py`**:
  - Implements `cancel_command()` function
  - Cancels one or more jobs
  - Sends cancellation requests to head node via API

- **`config.py`**:
  - Implements `config_command()` function
  - Manages configuration file
  - Subcommands: init, show, get, set
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
├── logging_config.py     # Logging configuration
└── head_info.py          # Head node connection information
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
    - `JobStatus`: enum (pending, running, completed, failed, cancelled)

- **`config.py`**:
  - Loads configuration from YAML file
  - Environment variable overrides
  - Default values
  - Configuration validation
  - Config class with all settings
  - HeadConfig and WorkerConfig dataclasses
  - Path resolution (~/.scheduler expansion)

- **`head_info.py`**:
  - Utilities for storing and retrieving head node connection information
  - `save_head_info()` - Saves head address to worker lock files
  - `load_head_info()` - Loads head address from active worker lock files
  - `clear_head_info()` - Clears stored head node addresses
  - Stores data in JSON format within worker lock files
  - Only returns address if worker process is still running

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
  - API endpoints (API_VERSION, API_BASE_PATH)
  - File paths
  - Status codes

- **`exceptions.py`**:
  - Custom exception classes
  - SchedulerException (base)
  - NodeNotFoundException
  - JobNotFoundException
  - InvalidRequirementException
  - ConnectionException
  - ValidationException
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
├── client.py             # HTTP client (SchedulerClient class)
├── routes.py             # API route definitions
└── schemas.py            # Request/response schemas (Pydantic)
```

**Purpose of each file:**

- **`client.py`**:
  - `SchedulerClient` class for HTTP communication
  - Used by CLI commands to interact with head node
  - Used by worker daemon to communicate with head node
  - Methods for all API endpoints:
    - Job operations: submit_job, get_job, list_jobs, cancel_job, get_job_logs
    - Node operations: register_node, send_heartbeat, list_nodes, get_node
    - Worker operations: poll_for_job, complete_job, fail_job
  - Connection pooling via requests.Session
  - Retry logic and error handling
  - Auto-discovery of head node address

- **`routes.py`**:
  - `create_app()` function to create FastAPI application
  - All API route definitions organized by category:
    - Health check: `/api/v1/health`
    - Job routes: POST/GET/DELETE `/api/v1/jobs`, `/api/v1/jobs/{job_id}`
    - Node routes: POST `/api/v1/nodes/register`, `/api/v1/nodes/{node_name}/heartbeat`
    - Worker routes: GET `/api/v1/workers/{node_name}/jobs/next`
  - Endpoint implementations with validation
  - Error handling and HTTP status codes
  - Long-polling support for job assignments
  - Integration with JobManager and NodeManager

- **`schemas.py`**:
  - Pydantic models for API requests/responses
  - Request schemas: JobSubmitRequest, NodeRegisterRequest, NodeHeartbeat
  - Response schemas: JobResponse, JobListResponse, NodeResponse
  - Validation logic
  - Serialization helpers
  - Type-safe data models for API communication

---

### 1.6 `scheduler/tui/` - Terminal User Interface

Interactive TUI for monitoring cluster status (similar to nvitop).

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
└── utils.py              # TUI utilities
```

**Note:** The TUI no longer uses separate widget modules. Widgets are defined inline within screens using Textual's built-in widgets (DataTable, Static, etc.).

**Purpose of each file:**

- **`app.py`**:
  - Main `SchedulerTUI` class extending Textual App
  - Keyboard binding definitions (q=quit, r=refresh, n=nodes, j=jobs, g=gpus, h=help)
  - Screen management and switching via actions
  - Auto-refresh timer (2s interval using set_interval)
  - Data fetching from head node API via SchedulerClient
  - Global state management (nodes_data, jobs_data)
  - CSS styling definitions
  - SCREENS registry for all available screens

- **`screens/cluster.py`**:
  - `ClusterScreen` - Default cluster overview screen
  - Composes: Header, summary panels, node table (DataTable), job list
  - Shows nodes, GPUs, and jobs summary
  - Keyboard bindings for switching views
  - Reactive data updates from app

- **`screens/nodes.py`**:
  - `NodesScreen` - Detailed node view (press 'N')
  - Composes: Header, node selector, per-GPU stats table
  - Shows selected node's GPU statistics
  - Running jobs on node
  - Node health information
  - Interactive node selection

- **`screens/jobs.py`**:
  - `JobsScreen` - Full jobs list (press 'J')
  - Composes: Header, jobs DataTable with filtering
  - Built-in Textual filtering and sorting
  - Search functionality using Textual Input widget
  - Job selection and detail navigation

- **`screens/gpus.py`**:
  - `GPUsScreen` - Detailed GPU view (press 'G')
  - Composes: Grid layout of GPU cards
  - All GPUs across all nodes
  - Per-GPU statistics with progress bars
  - Stability indicators (time free)
  - GPU utilization visualization

- **`screens/job_detail.py`**:
  - `JobDetailScreen` - Single job details (press Enter on job)
  - Composes: Vertical layout with labeled sections
  - Job metadata display (status, runtime, etc.)
  - Dependencies list
  - Environment variables
  - Action buttons (view logs, cancel, retry)

- **`utils.py`**:
  - Data formatting helpers (bytes to human-readable, time formatting)
  - Color scheme definitions for status indicators
  - GPU utilization bar creation helpers
  - API client wrapper utilities for TUI
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

Comprehensive test coverage for all components with **865 tests** and **88% overall coverage**.

```
tests/
├── __init__.py
├── README.md             # Comprehensive testing documentation
├── conftest.py           # Pytest fixtures and test configuration
├── unit/                 # Unit tests (671 tests, 100% pass rate)
│   ├── test_models.py
│   ├── test_config.py
│   ├── test_core_utils.py
│   ├── test_head_info.py
│   ├── test_head_info_clear.py
│   ├── test_logging_config.py
│   ├── test_scheduler.py
│   ├── test_job_manager.py
│   ├── test_node_manager.py
│   ├── test_orchestrator.py
│   ├── test_persistence.py
│   ├── test_storage_backends.py
│   ├── test_api_server.py
│   ├── test_api_routes_unit.py
│   ├── test_api_app_creation.py
│   ├── test_python_client.py
│   ├── test_cli_main.py
│   ├── test_cli_start.py
│   ├── test_cli_stop.py
│   ├── test_cli_submit.py
│   ├── test_cli_jobs.py
│   ├── test_cli_logs.py
│   ├── test_cli_cancel.py
│   ├── test_cli_status.py
│   ├── test_cli_helpers.py
│   ├── test_cli_config_cmd.py
│   ├── test_worker_gpu_monitor.py
│   ├── test_singleton.py
│   ├── test_worker_job_executor.py
│   ├── test_worker_heartbeat.py
│   ├── test_worker_file_handler.py
│   ├── test_worker_daemon.py
│   ├── test_tui_app_methods.py
│   ├── test_tui_app_integration.py
│   ├── test_tui_fixtures.py
│   ├── test_tui_screens.py
│   └── test_tui_utils.py
├── integration/          # Integration tests (177 tests, 100% pass rate)
│   ├── test_job_lifecycle.py
│   ├── test_api_endpoints.py
│   ├── test_cli_commands_integration.py
│   ├── test_full_workflow.py
│   └── test_tui_integration.py
├── e2e/                  # End-to-end tests (17 tests, 100% pass rate)
│   ├── test_cli_e2e.py
│   ├── test_python_api_complete.py
│   └── test_real_processes.py
└── contract/             # Contract testing (infrastructure only)
```

**Test Coverage Summary:**

- **Unit Tests:** 671 tests covering individual components
  - Core components: 93% coverage (models, config, utils)
  - Worker components: 87% coverage (daemon, GPU monitor, job executor)
  - Head components: 98% coverage (orchestrator, scheduler, managers)
  - Storage components: 97% coverage (file and SQLite backends)
  - CLI components: 85% coverage (all commands)
  - TUI components: 88% coverage (app, screens, utils)
  - API components: 80% coverage (client, routes, schemas)

- **Integration Tests:** 177 tests for component interactions
  - Job lifecycle workflows
  - API endpoint integration
  - CLI command integration
  - Full workflow simulation
  - TUI integration

- **E2E Tests:** 17 tests with real processes
  - Real head and worker processes with HTTP communication
  - Cluster startup and worker registration
  - Job submission, execution, and completion
  - Multiple jobs (sequential and concurrent)
  - Job cancellation, dependencies, environment variables
  - Job failure handling and log retrieval
  - **Note:** Requires real NVIDIA GPUs to run

**Test Infrastructure:**

- `conftest.py` - Shared pytest fixtures for all test categories
- `tests/README.md` - Comprehensive testing documentation including:
  - Test structure and organization
  - Running tests (pytest commands)
  - Coverage reports
  - Writing new tests
  - Mock specification guidelines
  - Common pitfalls and best practices
  - Current test status and roadmap

**Key Testing Features:**

- **Mock Specification Guidelines:** Comprehensive rules for proper mocking
  - Always use `autospec=True` for patches
  - Use `spec_set=True` for internal code mocks
  - Proper handling of external libraries
  - Property mocking patterns
  - Avoiding common pitfalls

- **Coverage Goals:**
  - Unit tests: >90% coverage for core modules ✅ Achieved
  - Integration tests: Cover all major workflows ✅ Achieved
  - E2E tests: Cover critical user scenarios ✅ Achieved

- **Test Categories:**
  - Unit tests: Test individual components in isolation
  - Integration tests: Test interactions between components
  - E2E tests: Test complete workflows from CLI to execution

---

## 3. `scripts/` - Utility Scripts

Helper scripts for development and deployment.

```
scripts/
└── (empty - placeholder for future utility scripts)
```

**Note:** The scripts directory exists but currently contains no active scripts. Future scripts may include:
- Installation helpers
- Development environment setup
- Test cluster startup scripts
- Cleanup utilities
- Performance benchmarking tools

---

## 4. `docs/` - Documentation

Additional documentation is located in the root directory.

```
docs/
└── (empty - documentation exists in root directory)
```

**Documentation files in root directory:**

- **`README.md`** - User-facing documentation and quick start guide
- **`API_REFERENCE.md`** - Comprehensive API documentation
- **`CODEBASE_STRUCTURE.md`** - This file - codebase organization
- **`dev_note.md`** - Development notes and guidelines
- **`CTRL_C_FIX.md`** - Documentation on Ctrl+C handling fixes
- **`E2E_PERFORMANCE_OPTIMIZATIONS.md`** - E2E test performance improvements
- **`TEST_IMPROVEMENTS_SUMMARY.md`** - Summary of test improvements
- **`TUI_BRANCH_COVERAGE_ANALYSIS.md`** - TUI test coverage analysis
- **`TUI_TESTING_RECOMMENDATIONS.md`** - TUI testing recommendations
- **`test_comprehensiveness_report.md`** - Test comprehensiveness report
- **`test_coverage_report.md`** - Detailed coverage report
- **`vulnerability_discovery_report.md`** - Security vulnerability analysis

**Note:** Example scripts and configs are currently not included but may be added in the future.

---

## 5. Root Files

- **`setup.py`**:
  - Package installation configuration
  - Entry point for CLI command: `scheduler=scheduler.cli.main:main`
  - Dependencies:
    - **fastapi** - Modern, fast ASGI framework for API server
    - **uvicorn** - Production-ready ASGI server
    - **requests** - Simple HTTP client
    - **pydantic** - Type-safe data models and validation
    - **pyyaml** - YAML configuration file parsing
    - **textual** - Interactive terminal UI framework
    - **click** - Command-line interface framework
    - **nvidia-ml-py** (pynvml) - NVIDIA Management Library bindings
    - **psutil** - Cross-platform process utilities
  - Development dependencies (extras_require):
    - **pytest** - Testing framework
    - **pytest-asyncio** - Async test support
    - **pytest-cov** - Coverage reporting
    - **black** - Code formatting
    - **ruff** - Fast Python linter
  - Package metadata (name, version, author, description)
  - Python version requirement: >=3.10

- **`requirements.txt`**:
  - Python dependencies for installation
  - Same core libraries as setup.py
  - Used for pip install -r requirements.txt

- **`requirements-dev.txt`**:
  - Development and testing dependencies
  - Includes pytest, pytest-asyncio, pytest-cov
  - Code quality tools (black, ruff)
  - Additional testing utilities

- **`README.md`**:
  - User-facing documentation
  - Quick start guide
  - Installation instructions
  - Basic usage examples
  - Architecture overview
  - Link to full documentation

- **`Makefile`**:
  - Common development tasks
  - Test execution shortcuts
  - Coverage report generation
  - Code quality checks

- **`pytest.ini`**:
  - Pytest configuration
  - Test markers (unit, integration, e2e, slow, gpu)
  - Coverage settings
  - Test discovery patterns

- **`.gitignore`**:
  - Python artifacts (__pycache__, *.pyc)
  - Virtual environments (venv/, env/)
  - IDE files (.vscode/, .idea/)
  - Coverage reports (htmlcov/, .coverage)
  - Log files and directories (log/, *.log)
  - Local config files
  - Build artifacts (dist/, build/, *.egg-info/)

- **Coverage Reports:**
  - `htmlcov/` - Unit test coverage HTML reports
  - `htmlcov_integration/` - Integration test coverage
  - `htmlcov_e2e/` - E2E test coverage
  - `htmlcov_tui_unit/`, `htmlcov_tui_integration/`, `htmlcov_tui_improved/` - TUI-specific coverage
  - `.coverage` - Coverage data file

- **Additional Directories:**
  - `log/` - Runtime log files
  - `reports/` - Test and analysis reports
  - `pacts/` - Contract testing artifacts
  - `gpu_scheduler.egg-info/` - Package metadata

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
2. **Testability**: Components are designed for easy testing with comprehensive test suite
3. **Extensibility**: Easy to add new features without modifying core
4. **Configuration**: Behavior controlled through config, not code changes
5. **Error Handling**: Graceful degradation and clear error messages
6. **Logging**: Comprehensive logging for debugging
7. **Documentation**: Code is self-documenting with clear naming
8. **Type Safety**: Extensive use of type hints and Pydantic models

---

*This structure provides a solid foundation for building and maintaining the GPU scheduler system.*
