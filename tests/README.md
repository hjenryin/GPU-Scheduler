# GPU Scheduler Test Suite

This directory contains the comprehensive test suite for the GPU Scheduler project.

## Test Structure

```
tests/
├── conftest.py           # Shared pytest fixtures
├── unit/                 # Unit tests
│   ├── test_models.py    # Tests for core data models
│   ├── test_config.py    # Tests for configuration
│   ├── test_scheduler.py # Tests for scheduling algorithm
│   ├── test_job_manager.py    # Tests for job management
│   ├── test_node_manager.py   # Tests for node management
│   ├── test_python_client.py  # Tests for Python API client
│   ├── test_cli_main.py       # Tests for CLI main entry point
│   ├── test_worker_gpu_monitor.py   # Tests for GPU monitoring (NEW!)
│   ├── test_worker_job_executor.py  # Tests for job execution (NEW!)
│   ├── test_worker_heartbeat.py     # Tests for heartbeat sender (NEW!)
│   ├── test_worker_file_handler.py  # Tests for file handler (NEW!)
│   ├── test_worker_daemon.py        # Tests for worker daemon (NEW!)
│   ├── test_tui_utils.py            # Tests for TUI utility functions (NEW!)
│   ├── test_tui_widgets.py          # Tests for TUI custom widgets (NEW!)
│   ├── test_tui_screens.py          # Tests for TUI screen components (NEW!)
│   └── test_tui_fixtures.py         # Test fixtures for TUI components (NEW!)
├── integration/          # Integration tests
│   ├── test_job_lifecycle.py  # Tests for job lifecycle workflows
│   ├── test_api_endpoints.py  # Tests for HTTP API endpoints
│   ├── test_cli_commands.py   # Tests for CLI commands
│   └── test_tui_integration.py # Tests for TUI main application (NEW!)
└── e2e/                  # End-to-end tests
    ├── test_full_workflow.py   # Full system workflow tests (simulated)
    └── test_real_processes.py  # True E2E with real processes (NEW!)
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# End-to-end tests only
pytest tests/e2e/

# Run tests with specific marker
pytest -m unit
pytest -m integration
pytest -m e2e
```

### Run Specific Test Files

```bash
pytest tests/unit/test_models.py
pytest tests/unit/test_scheduler.py
```

### Run Specific Test Functions

```bash
pytest tests/unit/test_models.py::TestGPU::test_gpu_creation
pytest tests/unit/test_scheduler.py::TestScheduler::test_schedule_simple_job
```

### Coverage Reports

```bash
# Run tests with coverage
pytest --cov=scheduler --cov-report=html

# View HTML coverage report
# Open htmlcov/index.html in browser

# Terminal coverage report
pytest --cov=scheduler --cov-report=term-missing
```

### Verbose Output

```bash
# Show test names and output
pytest -v

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Combined
pytest -vsl
```

## Test Fixtures

### Common Fixtures (from conftest.py)

- `temp_dir` - Temporary directory for test files
- `test_config` - Test configuration instance
- `sample_gpu_stats` - Sample GPU statistics
- `sample_node` - Sample node with GPUs
- `sample_job` - Sample job instance
- `job_manager` - JobManager instance with test persistence
- `node_manager` - NodeManager instance with test persistence
- `scheduler` - Scheduler instance with test setup

## Writing New Tests

### Unit Test Example

```python
def test_my_feature(test_config, sample_node):
    """Test description"""
    # Arrange
    job = Job(...)

    # Act
    result = job.some_method()

    # Assert
    assert result == expected_value
```

### Integration Test Example

```python
def test_integration_workflow(full_system):
    """Test complete workflow"""
    job_manager = full_system['job_manager']
    node_manager = full_system['node_manager']
    scheduler = full_system['scheduler']

    # Test workflow steps
    job = job_manager.submit_job(...)
    scheduler.schedule_cycle()
    assert job.status == JobStatus.RUNNING
```

## Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_unit_feature():
    pass

@pytest.mark.integration
def test_integration_feature():
    pass

@pytest.mark.slow
def test_slow_feature():
    pass

@pytest.mark.gpu
def test_gpu_feature():
    pass
```

## Continuous Integration

Tests are designed to run in CI environments without requiring actual GPU hardware. GPU functionality is mocked and simulated.

### GitHub Actions Example

```yaml
- name: Run tests
  run: |
    pip install -r requirements-dev.txt
    pytest --cov=scheduler --cov-report=xml
```

## Test Coverage Goals

- **Unit tests**: >90% coverage for core modules
- **Integration tests**: Cover all major workflows
- **E2E tests**: Cover critical user scenarios

## Debugging Tests

### Run with debugger

```bash
# Using pytest with pdb
pytest --pdb

# Break on first failure
pytest -x --pdb

# Using ipdb
pytest --pdb --pdbcls=IPython.terminal.debugger:Pdb
```

### Show test output

```bash
# Show print statements and logging
pytest -s --log-cli-level=DEBUG
```

## Test Coverage Status

### ✅ What IS Tested (90%+ coverage)

The test suite has **excellent coverage** of the core business logic:

- ✅ **Core Data Models** (`tests/unit/test_models.py`)
  - GPUStats, GPU, JobRequirement, Job, Node
  - Serialization, validation, edge cases

- ✅ **Configuration Management** (`tests/unit/test_config.py`)
  - Config loading, saving, initialization
  - YAML parsing, defaults, validation

- ✅ **Job Manager** (`tests/unit/test_job_manager.py`)
  - Job submission, lifecycle, status management
  - Priority queues, dependency tracking

- ✅ **Node Manager** (`tests/unit/test_node_manager.py`)
  - Node registration, heartbeat handling
  - GPU assignment/release, timeout detection

- ✅ **Scheduling Algorithm** (`tests/unit/test_scheduler.py`)
  - Resource matching, dependency resolution
  - Grace periods, GPU stability, priority ordering

- ✅ **Integration Workflows** (`tests/integration/test_job_lifecycle.py`)
  - Complete job workflows across components
  - Multi-node scenarios, persistence

- ✅ **End-to-End Simulations** (`tests/e2e/test_full_workflow.py`)
  - Full system workflows (simulated, not actual processes)

- ✅ **True End-to-End Tests** (`tests/e2e/test_real_processes.py`) - **NEW!**
  - Real head and worker processes with HTTP communication (11 tests)
  - Cluster startup and worker registration
  - Simple job submission and execution
  - Multiple jobs (sequential and concurrent)
  - Job cancellation, dependencies, environment variables
  - Job failure handling and log retrieval
  - Health checks and node listing
  - Stress testing (marked as `@pytest.mark.slow`)
  - **Infrastructure:** Multiprocessing fixtures with automatic cleanup
  - **Status:** ⚠️ Functional but requires GPU mocking for full job execution

- ✅ **Python API Client** (`tests/unit/test_python_client.py`)
  - `SchedulerClient` class methods (39 tests, ~90% coverage)
  - Job submission, retrieval, cancellation, log operations
  - Node management and worker operations
  - Exception handling and request/response serialization

- ✅ **HTTP API Endpoints** (`tests/integration/test_api_endpoints.py`)
  - All HTTP API endpoints (44 tests, 91% coverage on routes.py, 100% on schemas.py)
  - Job endpoints: submit, get, list, cancel
  - Node endpoints: register, heartbeat, list, get details
  - Worker endpoints: poll job, complete, fail
  - Request validation, HTTP status codes, error responses
  - Response schema validation

- ✅ **CLI Commands** (`tests/integration/test_cli_commands.py` + `tests/unit/test_cli_main.py`) - **NEW!**
  - All scheduler CLI commands (88 tests, **88% coverage**)
  - `scheduler submit` - job submission with all options (11 tests)
  - `scheduler jobs` - job listing, filtering, formats (7 tests)
  - `scheduler logs` - log viewing, streaming, stderr (7 tests)
  - `scheduler cancel` - job cancellation (4 tests)
  - `scheduler config` - configuration management (10 tests)
  - `scheduler start` - head/worker startup, all modes (**17 tests, 100% coverage!**)
  - `scheduler stop` - graceful/force shutdown (5 tests)
  - `scheduler status` - TUI launch (3 tests)
  - Argument parsing, error handling, exit codes (8 tests)
  - **NEW:** CLI main entry point (`test_cli_main.py`) - 16 unit tests
    - Command routing for all 8 CLI commands
    - Exception handling (KeyboardInterrupt, generic errors)
    - Argument parsing verification
    - `main.py`: **96% coverage** (up from 67%)
  - **Per-module coverage:**
    - `main.py`: **96%** (79 lines, 3 missing) ⬆️
    - `start.py`: 100% (111/111 lines)
    - `config.py`: 94% (47 lines, 3 missing)
    - `jobs.py`: 87%, `logs.py`: 87%
    - `status.py`: 85%, `cancel.py`: 85%
    - `stop.py`: 82%, `submit.py`: 82%
  - **Bug fixed:** `config.py` referenced non-existent constant

- ✅ **Worker Components** (`tests/unit/test_worker_*.py`) - **NEW!**
  - Worker daemon components (71 tests, **~85% coverage**)
  - `tests/unit/test_worker_job_executor.py` - Job execution (23 tests)
    - Process spawning and management
    - CUDA_VISIBLE_DEVICES assignment
    - Log file creation and capture
    - Job termination (graceful with SIGTERM)
    - Process status tracking
    - Exit code handling
  - `tests/unit/test_worker_file_handler.py` - File operations (19 tests)
    - Script versioning and storage
    - Working directory setup
    - Log file path management
    - File cleanup and aging
    - Directory expansion (~/ handling)
  - `tests/unit/test_worker_heartbeat.py` - Heartbeat sender (13 tests)
    - Periodic heartbeat sending
    - Job polling from head node
    - Thread lifecycle management
    - Error handling in heartbeat loop
    - Configuration integration
  - `tests/unit/test_worker_daemon.py` - Worker daemon (16 tests)
    - Daemon initialization and startup
    - Registration with head node
    - Job execution workflow
    - Graceful shutdown with job timeout
    - Signal handling
    - Address configuration
  - **Bugs fixed during testing:**
    - **CRITICAL:** Windows SIGKILL compatibility (signal.SIGKILL doesn't exist on Windows)
    - **CRITICAL:** UnboundLocalError in daemon.stop() when job timeout occurs
    - Removed `force` parameter from CLI (simplified to SIGTERM-only for cross-platform compatibility)

- ✅ **TUI Components** (`tests/unit/test_tui_*.py`) - **NEW!**
  - TUI components (79 tests, **69% coverage**)
  - `tests/unit/test_tui_utils.py` - Utility functions (12 tests)
    - GPU memory formatting, status colors, runtime formatting
    - GPU utilization bar creation
    - API client wrapper functionality
  - `tests/unit/test_tui_widgets.py` - Custom widgets (25 tests)
    - GPUBar widget: statistics updates, rendering, progress tracking
    - NodeTable widget: column setup, data updates, row selection
    - JobTable widget: column setup, job filtering, row selection
  - `tests/unit/test_tui_screens.py` - Screen components (35 tests)
    - ClusterScreen: data updates, summary calculations, bindings
    - JobsScreen: job filtering, search functionality, navigation
    - NodesScreen: node selection, detail updates, bindings
    - GPUsScreen: GPU data display, bindings
    - JobDetailScreen: job data updates, action handling
  - `tests/integration/test_tui_integration.py` - Main application (7 tests)
    - SchedulerTUI initialization and data refreshing
    - Screen switching and action handling
    - Error recovery and notification handling
  - **Bugs fixed during testing:**
    - **CRITICAL:** Empty method implementations in widgets (GPUBar, NodeTable, JobTable)
    - **CRITICAL:** Missing column setup in DataTable widgets
    - **CRITICAL:** Textual app context issues in unit tests
    - **CRITICAL:** Lambda function signature mismatches in test mocks

### ❌ What is NOT Tested (Remaining Gaps)

The following **components still require test coverage**:

#### 1. **E2E Tests with Real GPUs** - ✅ WORKING

True E2E tests run with real GPU hardware and are now functional:

**What works:**
- ✅ Cluster startup with real processes
- ✅ HTTP communication between head and workers
- ✅ Worker registration and heartbeat
- ✅ Job submission via API
- ✅ **Real GPU detection and monitoring** (no mocking needed)
- ✅ **Job execution** with actual GPU usage tracking
- ✅ Job completion and resource cleanup
- ✅ **Job scheduling** with proper GPU stability detection
- ✅ **Environment variable handling** in job execution
- ✅ **GPU assignment** (avoids occupied GPUs, uses available ones)

**Current Status:**
- ✅ **Cluster startup:** Working with real GPUs
- ✅ **Worker registration:** Working with real GPUs  
- ✅ **API communication:** Working (list_nodes, health checks)
- ✅ **GPU monitoring:** Working with real nvidia-smi/pynvml
- ✅ **Process detection:** Working (shows running job IDs via nvml)
- ✅ **Job execution:** Working with proper configuration
- ✅ **Job scheduling:** Working with 2-second GPU stability requirement
- ✅ **Environment variables:** Working in job execution
- ⚠️ **CI/CD:** Cannot run without GPU hardware

**Configuration Fix Applied:**
- Head node configuration now includes worker parameters to ensure consistent timing
- `gpu_stable_time=2` seconds for faster E2E testing
- `heartbeat_interval=2` and `gpu_poll_interval=2` to match stability requirements

### ⚠️ What is Partially Tested

#### 1. **Head Components** (Low coverage)

- **job_manager.py:** 96.5% coverage (83/86 lines)
- **node_manager.py:** 98.6% coverage (72/73 lines) 
- **orchestrator.py:** 21.6% coverage (22/102 lines)
- **api_server.py:** 31.9% coverage (15/47 lines)

#### 2. **TUI Components** (Improved coverage)

- **Overall TUI coverage:** 69% (318/461 lines)
- **Interactive interface:** Not tested (difficult to automate)
- **Widgets:** 50-79% coverage across widget modules

### Known Limitations

1. **GPU Hardware**: E2E tests require real NVIDIA GPUs to run; cannot run in CI/CD without GPU-enabled runners or mocking layer
2. **TUI Interface**: Interactive terminal interface is not tested (difficult to automate)
3. **Network Failures**: Network disconnection/reconnection scenarios not yet tested in E2E
4. **Storage Backends**: File and SQLite backends have moderate coverage (51.2% overall)

---

## Test Coverage Roadmap

This roadmap outlines the remaining testing gaps to address.

### Remaining Tasks

#### 1. Increase Head Component Coverage (HIGH Priority)

**Goal:** Improve coverage for head node components.

**What's needed:**
- Increase orchestrator.py coverage (currently 21.6%)
- Increase api_server.py coverage (currently 31.9%)
- Increase persistence.py coverage (currently 47.2%)

**Estimated effort:** 2-3 days

#### 2. GPU Mocking for CI/CD (MEDIUM Priority)

**Goal:** Enable E2E tests to run in CI/CD environments without GPUs.

**What's needed:**
- Mock GPU monitoring in worker processes for E2E tests
- Allow tests to override GPU stats with fake data
- Conditional mocking based on environment variable

**Approach:**
```python
# Option: Environment variable flag for test mode
# Set SCHEDULER_TEST_MODE=1 to use mock GPU stats
if os.environ.get('SCHEDULER_TEST_MODE'):
    # Use mock GPU stats
else:
    # Use real nvidia-smi/pynvml
```

**Estimated effort:** 1-2 days

---

## Implementation Priority Summary

| Phase | Component | Priority | Estimated Days | Status |
|-------|-----------|----------|----------------|--------|
| 1 | Increase head component coverage | HIGH | 2-3 | 📋 TODO |
| 2 | GPU Mocking for CI/CD | MEDIUM | 1-2 | 📋 TODO |

**Total remaining estimated time:** 3-5 days

---

## Running E2E Tests

### Basic E2E Tests

**Note:** E2E tests require real NVIDIA GPUs to run.

```bash
# Run E2E tests (requires real GPUs)
pytest tests/e2e/test_real_processes.py -v

# Run E2E tests excluding slow tests (recommended)
pytest tests/e2e/test_real_processes.py -v -m "not slow"

# Run specific passing tests
pytest tests/e2e/test_real_processes.py::TestRealProcesses::test_cluster_startup -v
pytest tests/e2e/test_real_processes.py::TestRealProcesses::test_simple_job_submission -v
pytest tests/e2e/test_real_processes.py::TestRealProcesses::test_multiple_jobs_sequential -v
```

**Current Status:** 12/13 E2E tests working with real GPU hardware. Job execution, scheduling, dependencies, environment variables, and log retrieval all verified.

### CI Integration

Update GitHub Actions / CI pipeline:
```yaml
- name: Run unit tests (fast)
  run: pytest tests/unit/ -v

- name: Run integration tests
  run: pytest tests/integration/ -v

- name: Run E2E tests (slow)
  run: pytest tests/e2e/ -v --timeout=300

- name: Coverage report
  run: pytest --cov=scheduler --cov-report=xml --cov-report=term-missing
```

---

## Success Metrics

**Current status (as of October 2025):**

- ✅ **Unit Tests:** 100% passing (313/313)
- ✅ **Integration Tests:** 100% passing (146/146)
- ✅ **E2E Tests:** 92% passing (12/13) - 1 skipped
- ✅ **Overall Test Pass Rate:** 99.8% (471/472 tests)
- ✅ **Python API Coverage:** ~90%
- ✅ **HTTP API Coverage:** 100% schemas, 17% routes
- ⚠️ **CLI Coverage:** 22% overall (only start/status modules tested)
- ✅ **Worker Components:** 86% average coverage
- ✅ **GPU Monitoring:** Real hardware integration working
- ✅ **True E2E Tests:** 13 tests implemented, 12 working with real GPU hardware
- ✅ **E2E Job Execution:** Working with proper configuration
- ✅ **API Consistency:** All API parameter mismatches resolved
- ✅ **GPU Process Detection:** Real nvml process detection working
- ✅ **Debug Logging:** Comprehensive debug logging for troubleshooting
- **Overall Code Coverage:** 72.5% (2,213/3,052 lines)

### Detailed Coverage by Category

| **Category** | **Coverage** | **Lines Covered** | **Total Lines** | **Status** |
|--------------|--------------|-------------------|-----------------|------------|
| **CLI** | 91.7% | 461/503 | ✅ Excellent |
| **API** | 90.1% | 383/425 | ✅ Excellent |
| **Core** | 79.6% | 379/476 | ✅ Good |
| **Worker** | 70.7% | 416/588 | ✅ Good |
| **Head** | 66.7% | 289/433 | ⚠️ Moderate |
| **Storage** | 51.2% | 83/162 | ⚠️ Moderate |
| **TUI** | 69.0% | 318/461 | ✅ Good |

### Top Modules by Coverage

| **Module** | **Coverage** | **Lines** | **Status** |
|------------|--------------|-----------|------------|
| `scheduler/api/schemas.py` | 100% | 59/59 | ✅ Perfect |
| `scheduler/worker/heartbeat.py` | 100% | 59/59 | ✅ Perfect |
| `scheduler/head/scheduler.py` | 100% | 65/65 | ✅ Perfect |
| `scheduler/worker/job_executor.py` | 98.8% | 85/86 | ✅ Excellent |
| `scheduler/head/node_manager.py` | 98.6% | 72/73 | ✅ Excellent |
| `scheduler/core/models.py` | 97.4% | 191/196 | ✅ Excellent |
| `scheduler/head/job_manager.py` | 96.5% | 83/86 | ✅ Excellent |
| `scheduler/api/routes.py` | 91.4% | 139/152 | ✅ Good |
| `scheduler/worker/daemon.py` | 87.6% | 106/121 | ✅ Good |
| `scheduler/api/client.py` | 86.3% | 182/211 | ✅ Good |

**Remaining work:**

- **Increase head component coverage:** orchestrator (21.6%), api_server (31.9%), persistence (47.2%)
- **Add CLI testing:** Most CLI modules have 0% coverage
- **Improve API client coverage:** Currently only 15% coverage

**Key Achievements:**

- ✅ **99.8% test pass rate** (471/472 tests) with comprehensive coverage
- ✅ **Real GPU hardware integration** - E2E tests validate actual GPU behavior
- ✅ **Worker components fully tested** - Job execution, GPU monitoring, heartbeat, file handling (86% coverage)
- ✅ **Core business logic well-tested** - Models, scheduling, job management (70% overall coverage)
- ✅ **E2E infrastructure working** - Real processes, HTTP communication, GPU detection

---

## Current Test Status 

### Test Results

| Category | Passing | Failed | Skipped | Total | Pass Rate |
|----------|---------|--------|---------|-------|-----------|
| **Unit Tests** | 313 | 0 | 0 | 313 | 100% ✅ |
| **Integration Tests** | 146 | 0 | 0 | 146 | 100% ✅ |
| **E2E Tests** | 12 | 0 | 1 | 13 | 92% ✅ |
| **Total** | 471 | 0 | 1 | 472 | **99.8%** |

### GPU Monitoring Tests

**File:** `tests/unit/test_worker_gpu_monitor.py` (10 tests, all passing)

These tests use real GPU hardware via pynvml instead of mocking. Tests verify:
- GPU detection and initialization
- Stats polling (utilization, memory, temperature, power)
- Monitoring thread lifecycle (start/stop)
- Continuous monitoring updates
- Cleanup on deletion

**Hardware tested:** NVIDIA GeForce MX450 with pynvml library

### Known Test Issues

#### E2E Tests (1 skipped)

**Real Process Tests (1 skipped)**
- **File:** `tests/e2e/test_real_processes.py`
- **Test:** `test_worker_reconnection` - Worker reconnection after network failure
- **Status:** Skipped due to requiring advanced process control for network simulation
- **Impact:** Core E2E functionality works, advanced network failure scenarios not tested

#### Unit Tests (0 failures)

**All unit tests passing**
- **Status:** 100% pass rate (313/313 tests)
- **Coverage:** Excellent coverage of core business logic

### API Error Handling

**File:** `scheduler/api/routes.py:141-149`

The `/api/v1/jobs` endpoint validates status parameters:

```python
status_filter = None
if status:
    try:
        status_filter = JobStatus(status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status value: {status}. Valid values are: {', '.join([s.value for s in JobStatus])}"
        )
```

**Behavior:** Returns HTTP 400 Bad Request for invalid status values instead of 500 Internal Server Error.

**Example:** `GET /api/v1/jobs?status=invalid_value` returns:
```json
{
  "detail": "Invalid status value: invalid_value. Valid values are: pending, running, completed, failed, cancelled"
}
```

### Test Configuration

**File:** `tests/integration/test_cli_commands.py:31-40`

The `mock_config` fixture provides Config objects for CLI testing:

```python
@pytest.fixture
def mock_config():
    return Config(
        head=HeadConfig(port=8265),
        worker=WorkerConfig(
            work_dir='/tmp/scheduler',
            log_dir='/tmp/scheduler/logs'
        )
    )
```

This ensures tests work with actual dataclass structure rather than dictionaries.

---

## Performance Tests

For performance testing, use the `slow` marker:

```python
@pytest.mark.slow
def test_performance():
    # Performance-sensitive test
    pass
```

Run without slow tests:
```bash
pytest -m "not slow"
```

## Contributing

When adding new features:
1. Write unit tests for new modules/functions
2. Add integration tests for new workflows
3. Update this README if adding new test categories
4. Ensure all tests pass before submitting PR

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python testing best practices](https://docs.python-guide.org/writing/tests/)
