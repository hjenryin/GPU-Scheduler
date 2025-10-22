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

## Known Issues and Limitations

1. **GPU Hardware**: Tests do not require actual GPUs - GPU functionality is mocked
2. **Network Communication**: API tests use in-process calls, not actual HTTP
3. **Process Execution**: Job execution is simulated, not actually run

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
