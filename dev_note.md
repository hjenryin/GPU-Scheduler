# Development Notes - TODOs Only

**⚠️ CRITICAL RULE: This file should ONLY contain TODOs and bugs that need to be fixed. NO other content allowed.**
**⚠️ When bugs are fixed, DELETE the entire entry - do not mark as complete or add notes.**
**⚠️ NO sections for "completed work", "notes", "status updates", or anything else.**

## Critical Priority (Must Fix)

## High Priority (Should Fix Soon)

### 🧪 Unit Test Isolation Issues
- **Issue**: Unit tests in `test_cli_main.py` are running actual command functions instead of mocks
- **Location**: `tests/unit/test_cli_main.py`
- **Impact**: Unit tests are slow, unreliable, and may interfere with running services
- **Fix Needed**: Unit tests should mock command functions to test CLI routing/parsing only. Actual command execution should be tested in integration tests.
- **Note**: Running actual commands IS important and should be tested - but in integration tests, not unit tests

### 🧪 Flaky Test: test_logging_config.py Causing Hangs
- **Issue**: When `test_logging_config.py` runs before `test_worker_daemon.py`, the test `test_stop_graceful_timeout_terminates_job` in `test_worker_daemon.py` hangs indefinitely
- **Location**: `tests/unit/test_logging_config.py` affects `tests/unit/test_worker_daemon.py::test_stop_graceful_timeout_terminates_job`
- **Impact**: Test execution order dependency - tests are not isolated, causing flaky test behavior
- **Fix Needed**: Investigate how logging configuration in `test_logging_config.py` is leaving global state that interferes with the daemon test's mocking/thread handling

## Medium Priority (Nice to Have)

### 📝 CLI Test Coverage
- **Issue**: Some CLI argument combinations not fully tested
- **Location**: CLI test suite
- **Impact**: Potential edge cases not covered
- **Fix Needed**: Add more comprehensive test cases for argument parsing

### 🔍 Error Message Improvements
- **Issue**: Some error messages could be more user-friendly
- **Location**: Various CLI commands
- **Impact**: Poor user experience when things go wrong
- **Fix Needed**: Review and improve error messages across CLI commands

## Low Priority (Future Enhancements)

### 📊 Configuration Validation
- **Issue**: Some config values not validated on startup
- **Location**: Configuration loading
- **Impact**: Runtime errors instead of startup validation
- **Fix Needed**: Add comprehensive config validation

