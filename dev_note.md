# Development Notes - TODOs Only

**⚠️ CRITICAL RULE: This file should ONLY contain TODOs and bugs that need to be fixed. NO other content allowed.**
**⚠️ When bugs are fixed, DELETE the entire entry - do not mark as complete or add notes.**
**⚠️ NO sections for "completed work", "notes", "status updates", or anything else.**

## Critical Priority (Must Fix)

### 🚨 Orchestrator Configuration Bug
- **Issue**: `heartbeat_timeout` is `None` causing `TypeError: unsupported type for timedelta seconds component: NoneType`
- **Location**: `scheduler/head/node_manager.py:172` in `check_timeouts()` method
- **Impact**: Prevents orchestrator from running properly, causes infinite error loops
- **Fix Needed**: Ensure `heartbeat_timeout` has a proper default value in config

## High Priority (Should Fix Soon)

### 🔧 Port Conflict Handling
- **Issue**: Port 8265 already in use during tests, causing `OSError: [Errno 98] address already in use`
- **Location**: Tests and orchestrator startup
- **Impact**: Tests fail, prevents multiple scheduler instances
- **Fix Needed**: Better port conflict detection and handling, or use different ports for testing

### 🧪 Unit Test Isolation Issues
- **Issue**: Unit tests in `test_cli_main.py` are running actual command functions instead of mocks
- **Location**: `tests/unit/test_cli_main.py`
- **Impact**: Unit tests are slow, unreliable, and may interfere with running services
- **Fix Needed**: Unit tests should mock command functions to test CLI routing/parsing only. Actual command execution should be tested in integration tests.
- **Note**: Running actual commands IS important and should be tested - but in integration tests, not unit tests

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

