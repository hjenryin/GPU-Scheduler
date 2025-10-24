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
│   └── test_worker_daemon.py        # Tests for worker daemon (NEW!)
├── integration/          # Integration tests
│   ├── test_job_lifecycle.py  # Tests for job lifecycle workflows
│   ├── test_api_endpoints.py  # Tests for HTTP API endpoints
│   └── test_cli_commands.py   # Tests for CLI commands
└── e2e/                  # End-to-end tests
    └── test_full_workflow.py   # Full system workflow tests
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

### ❌ What is NOT Tested (Critical Gaps)

The following **components still require test coverage**:

#### 1. **True End-to-End Tests** (0% coverage) - ⚠️ HIGH

Current E2E tests simulate workflows but don't test actual system integration:

**Missing tests:**

- Start actual head process (not in-memory)
- Start actual worker processes
- HTTP communication between real processes
- Process lifecycle management
- Network disconnection/reconnection
- Concurrent job execution
- Real GPU detection (with mocked nvidia-smi)

**Impact:** Integration issues between components running as separate processes may not be caught.

### ⚠️ What is Partially Tested

#### 2. **Environment Variables** (Mostly tested)

- ✅ Tested: `env_vars` parameter is stored in Job
- ✅ Tested: Environment variable propagation during job execution (worker tests)
- ✅ Tested: CUDA_VISIBLE_DEVICES assignment (worker tests)
- ❌ Missing: Actual subprocess receives correct environment (needs E2E test)

#### 3. **Job Timeout** (Partial coverage)

- ✅ Tested: `timeout` parameter is stored in Job
- ❌ Missing: Timeout enforcement during job execution
- ❌ Missing: Timeout cancellation logic

#### 4. **File Versioning** (Fully tested)

- ✅ Tested: `versioned_script_path` is assigned to Job
- ✅ Tested: Actual file copying and versioning logic (worker tests)
- ✅ Tested: Version cleanup and storage management (worker tests)

### Known Limitations

1. **GPU Hardware**: Tests do not require actual GPUs - GPU functionality is mocked
2. **Network Communication**: Tests use in-process function calls, not actual HTTP requests/responses
3. **Process Execution**: Job execution is simulated, not actually spawned as subprocesses
4. **TUI Interface**: Interactive terminal interface is not tested (difficult to automate)

---

## Test Coverage Roadmap

This roadmap outlines the remaining critical testing gaps to address.

### Phase 1: True End-to-End Tests (HIGH - Next Priority)

**Goal:** Test complete system with actual processes communicating via HTTP.

**New test file:** `tests/e2e/test_real_processes.py`

**Approach:**
- Use `multiprocessing` to start actual head and worker processes
- Test real HTTP communication
- Mock only external dependencies (nvidia-smi, job scripts)

**Example test structure:**

```python
import pytest
import multiprocessing
import time
from scheduler.head.daemon import run_head
from scheduler.worker.daemon import run_worker

@pytest.fixture(scope="module")
def running_cluster(tmp_path_factory):
    """Start actual head and worker processes"""
    temp_dir = tmp_path_factory.mktemp("cluster")

    # Start head process
    head_proc = multiprocessing.Process(
        target=run_head,
        kwargs={"port": 8265, "temp_dir": str(temp_dir)}
    )
    head_proc.start()
    time.sleep(2)  # Wait for startup

    # Start worker process
    worker_proc = multiprocessing.Process(
        target=run_worker,
        kwargs={
            "address": "localhost:8265",
            "num_gpus": 2,
            "temp_dir": str(temp_dir)
        }
    )
    worker_proc.start()
    time.sleep(2)

    yield {"head": head_proc, "worker": worker_proc}

    # Cleanup
    head_proc.terminate()
    worker_proc.terminate()
    head_proc.join()
    worker_proc.join()

def test_full_job_workflow_real_processes(running_cluster):
    """Test job submission through real HTTP"""
    from scheduler import SchedulerClient

    client = SchedulerClient(address="localhost:8265")

    # Submit job
    job = client.submit_job("echo 'test'", "1")
    assert job.job_id is not None

    # Wait for completion
    max_wait = 30
    for _ in range(max_wait):
        job = client.get_job(job.job_id)
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            break
        time.sleep(1)

    assert job.status == JobStatus.COMPLETED
```

**Test coverage targets:**
- Process startup and shutdown
- HTTP communication between processes
- Job execution across process boundaries
- Network error handling
- Concurrent job execution

**Estimated effort:** 5-7 days

---

## Implementation Priority Summary

| Phase | Component | Priority | Estimated Days | Status |
|-------|-----------|----------|----------------|--------|
| ~~1~~ | ~~Worker Tests~~ | ~~CRITICAL~~ | ~~7-10~~ | ✅ **COMPLETED** |
| 1 | True E2E Tests | HIGH | 5-7 | 📋 TODO |

**Remaining estimated time:** 5-7 days (1-1.5 weeks) for one developer

---

## Getting Started with Test Development

### 1. Set up test dependencies

All dependencies already in `requirements-dev.txt`:

```
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-asyncio>=0.21.0
pytest-mock>=3.11.0
```

### 2. Start with Phase 1 (True E2E Tests)

```bash
# Create test file
touch tests/e2e/test_real_processes.py

# Run only E2E tests during development
pytest tests/e2e/test_real_processes.py -v

# Check coverage
pytest tests/e2e/ --cov=scheduler --cov-report=term-missing
```

### 3. Use TDD approach

For each new test file:
1. Write test for simplest functionality
2. Run test (should fail)
3. Verify test catches the right thing
4. Repeat for all methods/scenarios

### 4. CI Integration

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

**Current status:**

- ✅ **Python API Coverage:** ~90% (ACHIEVED)
- ✅ **HTTP API Coverage:** 91% routes, 100% schemas (ACHIEVED)
- ✅ **CLI Coverage:** 88% overall, 96% for main.py (ACHIEVED)
- ✅ **Worker Components:** ~85% (ACHIEVED) - **NEW!**
- ❌ **True E2E Tests:** 0% (TODO)
- **Overall Coverage:** ~70% (up from ~62%)

**After completing remaining roadmap (Phase 1):**

- **True E2E Coverage:** Full system integration tested
- **Overall Coverage:** >75%

**Major Achievements:**

- ✅ **All three user-facing interfaces (Python API, CLI, HTTP) now have comprehensive test coverage!**
- ✅ **Worker components fully tested** - Job execution, GPU monitoring, heartbeat, file handling all validated
- ✅ **Critical bugs fixed** - Windows compatibility and daemon timeout issues resolved

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
