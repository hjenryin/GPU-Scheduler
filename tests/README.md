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
│   └── test_node_manager.py   # Tests for node management
├── integration/          # Integration tests
│   └── test_job_lifecycle.py  # Tests for job lifecycle workflows
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

### ❌ What is NOT Tested (Critical Gaps)

The following **user-facing interfaces require test coverage**:

#### 1. **CLI Commands** (0% coverage) - ⚠️ CRITICAL

All `scheduler` CLI commands are untested:

**Missing tests:**

- `scheduler start --head` - head node startup
- `scheduler start --address=...` - worker node startup
- `scheduler stop` - graceful shutdown
- `scheduler submit --req ... script.py` - job submission
- `scheduler jobs --filter running` - job listing
- `scheduler logs -f job_id` - log streaming
- `scheduler cancel job_id` - job cancellation
- `scheduler config init/show/set/get` - configuration commands
- `scheduler status` - TUI interface
- Argument parsing and validation
- Output formatting (table, JSON, YAML)
- Exit code handling

**Impact:** Users running CLI commands may encounter argument parsing errors, formatting issues, or unexpected behavior.

**Files:** `scheduler/cli/*.py` (~1000 lines total, 0% tested)

#### 2. **Worker Components** (0% coverage) - ⚠️ CRITICAL

Worker daemon components are untested:

**Missing tests:**

- GPU monitoring (`scheduler/worker/gpu_monitor.py`)
  - nvidia-smi parsing
  - GPU statistics collection
  - Stability detection
- Job executor (`scheduler/worker/job_executor.py`)
  - Process spawning and management
  - CUDA_VISIBLE_DEVICES assignment
  - Log capture and streaming
  - Exit code handling
- Heartbeat sender (`scheduler/worker/daemon.py`)
  - Periodic heartbeat sending
  - Connection retry logic
  - Job polling
- File handler (`scheduler/worker/file_handler.py`)
  - Script versioning and storage
  - Working directory setup

**Impact:** Actual job execution, GPU monitoring, and worker-head communication are not validated.

**Files:** `scheduler/worker/*.py` (~800 lines, 0% tested)

#### 3. **True End-to-End Tests** (0% coverage) - ⚠️ HIGH

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

#### 4. **Environment Variables** (Partial coverage)

- ✅ Tested: `env_vars` parameter is stored in Job
- ❌ Missing: Actual environment variable propagation during job execution
- ❌ Missing: CUDA_VISIBLE_DEVICES assignment verification

#### 5. **Job Timeout** (Partial coverage)

- ✅ Tested: `timeout` parameter is stored in Job
- ❌ Missing: Timeout enforcement during job execution
- ❌ Missing: Timeout cancellation logic

#### 6. **File Versioning** (Partial coverage)

- ✅ Tested: `versioned_script_path` is assigned to Job
- ❌ Missing: Actual file copying and versioning logic
- ❌ Missing: Version cleanup and storage management

### Known Limitations

1. **GPU Hardware**: Tests do not require actual GPUs - GPU functionality is mocked
2. **Network Communication**: Tests use in-process function calls, not actual HTTP requests/responses
3. **Process Execution**: Job execution is simulated, not actually spawned as subprocesses
4. **TUI Interface**: Interactive terminal interface is not tested (difficult to automate)

---

## Test Coverage Roadmap

This roadmap addresses the remaining critical testing gaps.

### Phase 1: CLI Command Tests (CRITICAL - Week 1-2)

**Goal:** Test CLI commands that users run in terminal.

**New test file:** `tests/integration/test_cli_commands.py`

**Approach:**
- Use `click.testing.CliRunner` for testing Click-based CLI
- Mock subprocess calls for start/stop commands
- Verify argument parsing, output formatting, exit codes

**Example test structure:**

```python
from click.testing import CliRunner
from scheduler.cli.main import cli
from unittest.mock import patch

class TestCLISubmit:
    def setup_method(self):
        self.runner = CliRunner()

    @patch('scheduler.cli.submit.SchedulerClient')
    def test_submit_simple_job(self, mock_client_class):
        """Test: scheduler submit --req 2 train.py"""
        mock_client = mock_client_class.return_value
        mock_client.submit_job.return_value = Mock(
            job_id="job_123",
            status=JobStatus.PENDING
        )

        result = self.runner.invoke(cli, [
            'submit', '--req', '2', 'train.py'
        ])

        assert result.exit_code == 0
        assert "job_123" in result.output
        mock_client.submit_job.assert_called_once_with(
            script="train.py",
            requirements="2",
            name=None,
            # ... other args
        )

    def test_submit_invalid_requirements(self):
        """Test invalid --req shows error"""
        result = self.runner.invoke(cli, [
            'submit', '--req', '', 'train.py'
        ])

        assert result.exit_code != 0
        assert "Invalid requirement" in result.output

class TestCLIJobs:
    @patch('scheduler.cli.jobs.SchedulerClient')
    def test_jobs_list_table_format(self, mock_client_class):
        """Test: scheduler jobs (default table format)"""
        mock_client = mock_client_class.return_value
        mock_client.list_jobs.return_value = [
            Mock(job_id="job_1", name="test", status=JobStatus.RUNNING)
        ]

        result = self.runner.invoke(cli, ['jobs'])

        assert result.exit_code == 0
        assert "job_1" in result.output
```

**Test coverage targets:**
- All CLI commands in `scheduler/cli/`
- Argument parsing and validation
- Output formatting (table, JSON, YAML)
- Exit codes
- Error messages

**Estimated effort:** 5-7 days

### Phase 2: Worker Component Tests (CRITICAL - Week 3-4)

**Goal:** Test worker daemon components that execute jobs.

**New test files:**
- `tests/unit/test_worker_gpu_monitor.py`
- `tests/unit/test_worker_job_executor.py`
- `tests/unit/test_worker_daemon.py`

**Approach:**
- Mock `subprocess` calls to nvidia-smi
- Mock `subprocess.Popen` for job execution
- Test GPU monitoring, job execution, heartbeat logic

**Example test structure:**

```python
from scheduler.worker.gpu_monitor import GPUMonitor
from unittest.mock import patch, Mock

class TestGPUMonitor:
    @patch('scheduler.worker.gpu_monitor.subprocess.run')
    def test_collect_gpu_stats(self, mock_run):
        """Test nvidia-smi parsing"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""
0, 10, 1024, 16384, 45, 50
1, 95, 15000, 16384, 78, 200
"""
        )

        monitor = GPUMonitor()
        stats = monitor.collect_gpu_stats()

        assert len(stats) == 2
        assert stats[0].gpu_id == 0
        assert stats[0].utilization == 10
        assert stats[1].utilization == 95

class TestJobExecutor:
    @patch('scheduler.worker.job_executor.subprocess.Popen')
    def test_execute_job_success(self, mock_popen):
        """Test successful job execution"""
        mock_process = Mock()
        mock_process.wait.return_value = 0
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        executor = JobExecutor()
        exit_code = executor.execute_job(
            script="train.py",
            assigned_gpus=[0, 1],
            env_vars={"KEY": "value"}
        )

        assert exit_code == 0
        # Verify CUDA_VISIBLE_DEVICES was set
        call_kwargs = mock_popen.call_args[1]
        assert call_kwargs['env']['CUDA_VISIBLE_DEVICES'] == '0,1'
```

**Test coverage targets:**
- GPU monitoring and nvidia-smi parsing
- Job execution with process management
- CUDA_VISIBLE_DEVICES assignment
- Log capture and streaming
- Heartbeat sending logic
- File versioning

**Estimated effort:** 7-10 days

### Phase 3: True End-to-End Tests (HIGH - Week 5-6)

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

### Phase 4: Partial Coverage Improvements (MEDIUM - Week 7)

**Goal:** Fill in partial test coverage gaps.

**Areas to address:**
- Environment variable propagation verification
- Job timeout enforcement testing
- File versioning and cleanup testing

**New tests to add:**
- `test_env_vars_propagation` in `test_worker_job_executor.py`
- `test_timeout_enforcement` in `test_worker_job_executor.py`
- `test_file_versioning` in `test_worker_file_handler.py`

**Estimated effort:** 3-5 days

---

## Implementation Priority Summary

| Phase | Component | Priority | Estimated Days | Dependencies |
|-------|-----------|----------|----------------|--------------|
| 1 | CLI Tests | CRITICAL | 5-7 | None |
| 2 | Worker Tests | CRITICAL | 7-10 | None |
| 3 | True E2E Tests | HIGH | 5-7 | Phases 1-2 |
| 4 | Partial Coverage | MEDIUM | 3-5 | Phase 2 |

**Total estimated time:** 21-32 days (4-6 weeks) for one developer

---

## Getting Started with Test Development

### 1. Set up test dependencies

Add to `requirements-dev.txt`:
```
pytest>=7.0
pytest-cov>=4.0
pytest-asyncio>=0.21
pytest-mock>=3.10
responses>=0.23  # For mocking HTTP requests
```

### 2. Start with Phase 1 (CLI Commands)

```bash
# Create test file
touch tests/integration/test_cli_commands.py

# Run only this test file during development
pytest tests/integration/test_cli_commands.py -v

# Check coverage
pytest tests/integration/test_cli_commands.py --cov=scheduler.cli --cov-report=term-missing
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
- **CLI Coverage:** 0% (TODO)
- **Worker Components:** 0% (TODO)
- **Overall Coverage:** ~50%

**After completing the roadmap:**
- **CLI Coverage:** >80%
- **Worker Components:** >85%
- **Overall Coverage:** >70%

Most importantly: **All three user-facing interfaces (Python API, CLI, HTTP) will have test coverage**, significantly reducing the risk of bugs in production. Two of three interfaces are now complete!

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
