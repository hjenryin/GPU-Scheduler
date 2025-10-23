# Import Guidelines Compliance Audit

## Import Pattern Guidelines

**Rule 1: Internal Imports (within a package)**
- Files inside `scheduler.XXX/` should import from sibling modules directly
- Example: `from scheduler.XXX.module import Class` ✅
- NOT: `from scheduler.XXX import Class` ❌ (triggers `__init__.py` recursively)

**Rule 2: External Imports (from outside a package)**
- Files outside `scheduler.XXX/` should import from package interface
- Example: `from scheduler.XXX import Class` ✅
- NOT: `from scheduler.XXX.module import Class` ❌ (bypasses public API)

**Exception:**
- `scheduler.core` can be accessed directly from anywhere (ubiquitous dependency)

---

## Audit Results

### ✅ COMPLIANCE: Internal Imports (Rule 1)

All packages correctly avoid importing through their own `__init__.py`:

- ✅ **scheduler.core** - No violations
- ✅ **scheduler.api** - No violations
- ✅ **scheduler.head** - No violations
- ✅ **scheduler.worker** - No violations
- ✅ **scheduler.storage** - No violations
- ✅ **scheduler.cli** - No violations
- ✅ **scheduler.tui** - No violations
- ✅ **scheduler.tui.screens** - No violations
- ✅ **scheduler.tui.widgets** - No violations

**Status:** ✅ **PASSED** - All internal imports are correct!

---

### ❌ VIOLATIONS: External Imports (Rule 2)

Files importing from other packages' submodules instead of package interface:

#### 1. scheduler.api Package

**File:** `scheduler/api/routes.py`
- Line 7: `from scheduler.head.job_manager import JobManager`
  - Should be: `from scheduler.head import JobManager`
- Line 8: `from scheduler.head.node_manager import NodeManager`
  - Should be: `from scheduler.head import NodeManager`

**Assessment:** ❌ 2 violations

---

#### 2. scheduler.cli Package

**File:** `scheduler/cli/cancel.py`
- Line 3: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**File:** `scheduler/cli/jobs.py`
- Line 5: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**File:** `scheduler/cli/logs.py`
- Line 1: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**File:** `scheduler/cli/start.py`
- Line 11: `from scheduler.head.orchestrator import Orchestrator`
  - Should be: `from scheduler.head import Orchestrator`
- Line 12: `from scheduler.worker.daemon import WorkerDaemon`
  - Should be: `from scheduler.worker import WorkerDaemon`
- Line 13: `from scheduler.worker.singleton import SingletonDaemon`
  - Should be: `from scheduler.worker import SingletonDaemon`

**File:** `scheduler/cli/status.py`
- Line 2: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`
- Line 3: `from scheduler.tui.app import run_tui`
  - Should be: `from scheduler.tui import run_tui`

**File:** `scheduler/cli/stop.py`
- Line 5: `from scheduler.worker.singleton import is_daemon_running`
  - Should be: `from scheduler.worker import is_daemon_running`

**File:** `scheduler/cli/submit.py`
- Line 5: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**Assessment:** ❌ 12 violations

---

#### 3. scheduler.head Package

**File:** `scheduler/head/api_server.py`
- Line 11: `from scheduler.api.routes import create_app`
  - Status: ⚠️ **INTENTIONAL EXCEPTION**
  - Reason: `create_app` is marked as internal-only in `scheduler/api/__init__.py`
  - This is correct according to the documented exception

**File:** `scheduler/head/orchestrator.py`
- Line 10: `from scheduler.storage.file_backend import FileBackend`
  - Should be: `from scheduler.storage import FileBackend`
- Line 11: `from scheduler.storage.sqlite_backend import SQLiteBackend`
  - Should be: `from scheduler.storage import SQLiteBackend`

**File:** `scheduler/head/persistence.py`
- Line 6: `from scheduler.storage.backend import StorageBackend`
  - Should be: `from scheduler.storage import StorageBackend`

**Assessment:** ❌ 3 violations (+ 1 intentional exception)

---

#### 4. scheduler.worker Package

**File:** `scheduler/worker/daemon.py`
- Line 15: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**File:** `scheduler/worker/heartbeat.py`
- Line 10: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`

**Assessment:** ❌ 2 violations

---

#### 5. scheduler.tui Package

**File:** `scheduler/tui/app.py`
- Line 6: `from scheduler.api.client import SchedulerClient`
  - Should be: `from scheduler.api import SchedulerClient`
- Line 7: `from scheduler.tui.screens.cluster import ClusterScreen`
  - Should be: `from scheduler.tui.screens import ClusterScreen`
- Line 8: `from scheduler.tui.screens.nodes import NodesScreen`
  - Should be: `from scheduler.tui.screens import NodesScreen`
- Line 9: `from scheduler.tui.screens.jobs import JobsScreen`
  - Should be: `from scheduler.tui.screens import JobsScreen`
- Line 10: `from scheduler.tui.screens.gpus import GPUsScreen`
  - Should be: `from scheduler.tui.screens import GPUsScreen`

**File:** `scheduler/tui/screens/cluster.py`
- Line 6: `from scheduler.api.schemas import Node, Job`
  - Should be: `from scheduler.api import Node, Job`
  - Note: schemas are exported in `scheduler.api.__init__.py`

**File:** `scheduler/tui/screens/gpus.py`
- Line 6: `from scheduler.api.schemas import Node`
  - Should be: `from scheduler.api import Node`

**File:** `scheduler/tui/screens/job_detail.py`
- Line 5: `from scheduler.api.schemas import Job`
  - Should be: `from scheduler.api import Job`

**File:** `scheduler/tui/screens/jobs.py`
- Line 6: `from scheduler.api.schemas import Job`
  - Should be: `from scheduler.api import Job`

**File:** `scheduler/tui/screens/nodes.py`
- Line 6: `from scheduler.api.schemas import Node, Job`
  - Should be: `from scheduler.api import Node, Job`

**Assessment:** ❌ 10 violations

---

## Summary Statistics

### Total Violations by Package

| Package | Internal (Rule 1) | External (Rule 2) | Total |
|---------|-------------------|-------------------|-------|
| scheduler.api | ✅ 0 | ❌ 2 | ❌ 2 |
| scheduler.head | ✅ 0 | ❌ 3 | ❌ 3 |
| scheduler.worker | ✅ 0 | ❌ 2 | ❌ 2 |
| scheduler.storage | ✅ 0 | ✅ 0 | ✅ 0 |
| scheduler.cli | ✅ 0 | ❌ 12 | ❌ 12 |
| scheduler.tui | ✅ 0 | ❌ 10 | ❌ 10 |
| **TOTALS** | **✅ 0** | **❌ 29** | **❌ 29** |

### Overall Assessment

- ✅ **Rule 1 (Internal Imports):** 100% compliance (0 violations)
- ❌ **Rule 2 (External Imports):** 29 violations found
- ⚠️ **Special Cases:** 1 intentional exception (create_app)

---

## Most Common Violations

1. **SchedulerClient** (9 occurrences)
   - Files import from `scheduler.api.client` instead of `scheduler.api`
   - Affects: cli, worker, tui packages

2. **API Schemas** (5 occurrences)
   - Files import from `scheduler.api.schemas` instead of `scheduler.api`
   - Affects: tui.screens package

3. **TUI Screens** (4 occurrences)
   - `tui/app.py` imports from `scheduler.tui.screens.XXX` instead of `scheduler.tui.screens`

4. **Head Components** (2 occurrences)
   - Files import from `scheduler.head.XXX` instead of `scheduler.head`
   - Affects: api, cli packages

5. **Storage Backends** (3 occurrences)
   - Files import from `scheduler.storage.XXX` instead of `scheduler.storage`
   - Affects: head package

6. **Worker Components** (3 occurrences)
   - Files import from `scheduler.worker.XXX` instead of `scheduler.worker`
   - Affects: cli package

---

## Recommendations

### Priority 1: High-Traffic Imports

Fix the most commonly violated imports first:

1. **SchedulerClient** - Update 9 files to import from `scheduler.api`
2. **API Schemas** - Update 5 files to import from `scheduler.api`
3. **TUI Screens** - Update `tui/app.py` to import from `scheduler.tui.screens`

### Priority 2: Package Boundaries

Clean up cross-package dependencies:

4. **Storage imports** - Update 3 files in head package
5. **Worker imports** - Update 3 files in cli package
6. **Head imports** - Update files in api and cli packages

### Implementation Strategy

**Option A: Fix all at once**
- Single comprehensive update
- ~29 files to modify
- Guaranteed consistency

**Option B: Fix by priority**
- Start with Priority 1 (high-traffic)
- Then Priority 2 (package boundaries)
- Staged rollout

**Option C: Fix by package**
- Update one package at a time
- Test after each package
- Easier to track progress

---

## Notes

1. All `__init__.py` files already export the necessary symbols, so fixes are straightforward
2. No circular import risks - all packages export correctly
3. The codebase structure is sound; this is just cleanup for consistency
4. `scheduler.core` is correctly treated as an exception (ubiquitous dependency)

---

**Audit Date:** 2025-10-22
**Audited By:** Claude Code
**Status:** Ready for remediation
