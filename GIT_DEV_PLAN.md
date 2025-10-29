# Git-Based Job Configuration Snapshot Implementation Plan

## Problem Statement

When jobs are submitted to the GPU scheduler, they may remain in the pending queue for some time before execution. During this time, configuration files (scripts, config files, etc.) in the user's working directory might change. If a job runs with modified files instead of the original files that existed at submission time, this can lead to:

1. **Inconsistent results**: The job runs with different code/config than intended
2. **Debugging difficulties**: Hard to reproduce issues when files have changed
3. **Unintended behavior**: Jobs may fail or produce wrong results due to file changes

## Solution: Git-Based Configuration Snapshot

Capture a snapshot of relevant files at job submission time using git, then restore that snapshot when the job starts executing. This ensures jobs always run with the exact files that existed when they were submitted.

## User Interface

### CLI Changes

No changes to the existing CLI interface. The feature works transparently:

```bash
# Existing command - no changes needed
scheduler submit --req 2 train.py

# The system will automatically:
# 1. Detect if the working directory is a git repository
# 2. Create a snapshot of the current state
# 3. Store the snapshot reference with the job
# 4. Restore the snapshot when the job runs
```

### Configuration Options (Optional Enhancement)

Add optional configuration in `~/.scheduler/config.yaml`:

```yaml
job_snapshot:
  enabled: true  # Enable/disable git snapshots (default: true)
  max_snapshot_size_mb: 100  # Maximum size for snapshot (default: 100MB)
  exclude_patterns:  # Files to exclude from snapshot
    - "*.pyc"
    - "__pycache__/"
    - ".pytest_cache/"
    - "*.log"
```

## Implementation Details

### Key Files and Functions

#### 1. New File: `scheduler/worker/git_snapshot.py`

**Purpose**: Handle git-based snapshots of job working directories

**Key Classes/Functions**:

```python
class GitSnapshotManager:
    """Manages git-based snapshots for job isolation"""
    
    def __init__(self, config: Config):
        """Initialize with configuration"""
        
    def is_git_repository(self, path: str) -> bool:
        """Check if path is inside a git repository"""
        
    def create_snapshot(self, job_id: str, working_dir: str) -> Optional[str]:
        """
        Create a git snapshot of the working directory.
        
        Returns:
            Snapshot reference (commit SHA or stash reference) or None if not a git repo
        """
        
    def restore_snapshot(self, job_id: str, snapshot_ref: str, working_dir: str) -> bool:
        """
        Restore files from snapshot to a temporary location.
        
        Returns:
            True if successful, False otherwise
        """
        
    def cleanup_snapshot(self, job_id: str, snapshot_ref: str) -> None:
        """Clean up snapshot after job completion"""
```

#### 2. Modified File: `scheduler/core/models.py`

**Changes to Job class**:

```python
class Job:
    # Add new fields:
    snapshot_ref: Optional[str] = None  # Git snapshot reference (SHA/stash)
    snapshot_working_dir: Optional[str] = None  # Original working dir for snapshot
    
    # Update to_dict() and from_dict() to include new fields
```

#### 3. Modified File: `scheduler/head/job_manager.py`

**Changes to `submit_job()` method**:

```python
def submit_job(self, ...) -> Job:
    """Submit a new job - now with git snapshot support"""
    
    # Existing code...
    
    # NEW: Create git snapshot if in git repository
    git_manager = GitSnapshotManager(self.config)
    if git_manager.is_git_repository(working_dir):
        snapshot_ref = git_manager.create_snapshot(job_id, working_dir)
        if snapshot_ref:
            job.snapshot_ref = snapshot_ref
            job.snapshot_working_dir = working_dir
            logger.info(f"Created git snapshot {snapshot_ref} for job {job_id}")
    
    # Rest of existing code...
```

#### 4. Modified File: `scheduler/worker/job_executor.py`

**Changes to `execute_job()` method**:

```python
def execute_job(self, job: Job, gpu_ids: List[int]) -> int:
    """Execute a job - now with git snapshot restoration"""
    
    # NEW: Restore git snapshot if available
    actual_working_dir = job.working_dir
    if job.snapshot_ref and job.snapshot_working_dir:
        git_manager = GitSnapshotManager(self.config)
        temp_dir = self.file_handler.get_job_snapshot_dir(job.job_id)
        if git_manager.restore_snapshot(job.job_id, job.snapshot_ref, temp_dir):
            actual_working_dir = temp_dir
            logger.info(f"Restored git snapshot {job.snapshot_ref} for job {job.job_id}")
        else:
            logger.warning(f"Failed to restore snapshot, using original directory")
    
    # Use actual_working_dir instead of job.working_dir
    working_dir = actual_working_dir or os.path.dirname(os.path.abspath(job.script))
    
    # Rest of existing code...
```

#### 5. Modified File: `scheduler/worker/file_handler.py`

**New method**:

```python
def get_job_snapshot_dir(self, job_id: str) -> str:
    """Get directory path for job snapshot restoration"""
    snapshot_dir = os.path.join(self.temp_dir, "snapshots", job_id)
    os.makedirs(snapshot_dir, exist_ok=True)
    return snapshot_dir
```

### Git Snapshot Strategy

We'll use **git stash** for creating lightweight snapshots:

1. **At job submission (head node)**:
   ```bash
   # Stash current state including untracked files
   git stash push -u -m "job-snapshot-{job_id}"
   # Get stash reference
   git stash list --max-count=1
   # Immediately pop the stash to restore user's working directory
   git stash pop
   ```

2. **At job execution (worker node)**:
   ```bash
   # Clone the repository to temp directory
   git clone <repo_path> <temp_dir>
   cd <temp_dir>
   # Apply the stash
   git stash apply <stash_ref>
   ```

**Alternative approach (for better isolation)**:
Use `git worktree` to create a separate working directory:
```bash
# Create worktree at temp location
git worktree add <temp_dir> <commit_sha>
```

### Interaction with Existing Functions

```
Job Submission Flow (Modified):
┌─────────────────────────────────────────────────────────┐
│ 1. User: scheduler submit --req 2 train.py             │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 2. submit_command() in cli/submit.py                   │
│    - Validates script path                              │
│    - Calls client.submit_job()                          │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 3. SchedulerClient.submit_job() in api/client.py       │
│    - Sends HTTP request to head node                    │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 4. JobManager.submit_job() in head/job_manager.py      │
│    - Creates Job object                                 │
│    - **NEW: Creates git snapshot if in git repo**       │
│    - Stores job in queue                                │
│    - Persists to storage                                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Job waits in pending queue...                       │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Scheduler assigns job to worker node                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│ 7. JobExecutor.execute_job() in worker/job_executor.py │
│    - **NEW: Restores git snapshot if available**        │
│    - Sets up environment variables                      │
│    - Executes job script                                │
└─────────────────────────────────────────────────────────┘
```

## Testing Strategy

### Unit Tests

#### `tests/unit/test_git_snapshot.py`

Test the GitSnapshotManager class in isolation:

```python
class TestGitSnapshotManager:
    def test_is_git_repository_returns_true_for_git_repo(self):
        """Test detection of git repository"""
        
    def test_is_git_repository_returns_false_for_non_git_dir(self):
        """Test detection of non-git directory"""
        
    def test_create_snapshot_returns_ref_for_git_repo(self):
        """Test snapshot creation in git repo"""
        
    def test_create_snapshot_returns_none_for_non_git_repo(self):
        """Test snapshot creation in non-git directory"""
        
    def test_restore_snapshot_creates_temp_directory(self):
        """Test snapshot restoration"""
        
    def test_restore_snapshot_handles_missing_ref(self):
        """Test handling of invalid snapshot reference"""
        
    def test_cleanup_snapshot_removes_temp_files(self):
        """Test cleanup of snapshot files"""
```

#### `tests/unit/test_job_manager_snapshot.py`

Test job manager integration:

```python
class TestJobManagerWithSnapshot:
    def test_submit_job_creates_snapshot_in_git_repo(self):
        """Test that job submission creates snapshot for git repos"""
        
    def test_submit_job_no_snapshot_in_non_git_dir(self):
        """Test that job submission works without git"""
        
    def test_job_model_includes_snapshot_fields(self):
        """Test Job model serialization with snapshot fields"""
```

#### `tests/unit/test_job_executor_snapshot.py`

Test job executor integration:

```python
class TestJobExecutorWithSnapshot:
    def test_execute_job_restores_snapshot(self):
        """Test job execution with snapshot restoration"""
        
    def test_execute_job_without_snapshot(self):
        """Test job execution without snapshot (backward compatibility)"""
        
    def test_execute_job_snapshot_restoration_failure(self):
        """Test graceful fallback when snapshot restoration fails"""
```

### Integration Tests

#### `tests/integration/test_git_snapshot_integration.py`

Test end-to-end workflow:

```python
class TestGitSnapshotIntegration:
    def test_job_with_file_changes_uses_snapshot(self):
        """
        1. Create git repo with script
        2. Submit job
        3. Modify script file
        4. Verify job runs with original script (from snapshot)
        """
        
    def test_non_git_job_works_as_before(self):
        """
        1. Create non-git directory with script
        2. Submit job
        3. Verify job runs normally
        """
        
    def test_snapshot_cleanup_after_job_completion(self):
        """
        1. Submit job with snapshot
        2. Wait for completion
        3. Verify snapshot cleanup
        """
```

## Implementation Phases

### Phase 1: Core Git Snapshot Functionality
- [ ] Implement `GitSnapshotManager` class
- [ ] Add unit tests for `GitSnapshotManager`
- [ ] Verify git operations work correctly

### Phase 2: Job Model Integration
- [ ] Add snapshot fields to `Job` model
- [ ] Update serialization/deserialization
- [ ] Add unit tests for model changes

### Phase 3: Job Submission Integration
- [ ] Modify `JobManager.submit_job()` to create snapshots
- [ ] Add logging for snapshot creation
- [ ] Add unit tests for submission with snapshots

### Phase 4: Job Execution Integration
- [ ] Modify `JobExecutor.execute_job()` to restore snapshots
- [ ] Update `FileHandler` to support snapshot directories
- [ ] Add unit tests for execution with snapshots

### Phase 5: Integration Testing
- [ ] Create integration tests for end-to-end workflow
- [ ] Test with modified files
- [ ] Test backward compatibility (non-git repos)

### Phase 6: Cleanup and Documentation
- [ ] Implement snapshot cleanup after job completion
- [ ] Add configuration options
- [ ] Update API documentation

## Risks and Mitigations

### Risk 1: Large Repository Size
**Issue**: Large git repositories may cause performance issues or disk space problems.

**Mitigation**: 
- Add configuration option for max snapshot size
- Skip snapshot creation if repo is too large
- Use shallow clones for snapshot restoration

### Risk 2: Git Not Available
**Issue**: Git may not be installed on all nodes.

**Mitigation**:
- Check for git availability before attempting snapshot
- Gracefully fall back to original behavior if git is not available
- Log warning when git is not available

### Risk 3: Private/Shared Files
**Issue**: Git snapshot may include sensitive files or very large files.

**Mitigation**:
- Respect .gitignore patterns
- Add exclude patterns configuration
- Only snapshot tracked files by default

### Risk 4: Cross-Node Access
**Issue**: Worker nodes may not have access to the original git repository.

**Mitigation**:
- Store snapshot metadata in job definition
- Use git archive or bundle for portable snapshots
- Consider storing snapshot in shared location if available

### Risk 5: Backward Compatibility
**Issue**: Existing jobs/code should continue to work.

**Mitigation**:
- Make snapshot feature optional (controlled by config)
- Ensure all new fields have sensible defaults
- Fall back to original behavior if snapshot fails

## Future Enhancements

1. **Selective File Snapshotting**: Allow users to specify which files to include in snapshot
2. **Snapshot Compression**: Compress snapshots to save space
3. **Snapshot Sharing**: Share snapshots between jobs with same files
4. **UI Feedback**: Show snapshot status in TUI/CLI
5. **Snapshot History**: Keep history of snapshots for debugging

## Success Criteria

1. ✅ Jobs in git repositories automatically get file snapshots
2. ✅ Jobs run with original files even if files change while pending
3. ✅ Non-git jobs continue to work as before (backward compatible)
4. ✅ All unit tests pass
5. ✅ All integration tests pass
6. ✅ No performance degradation for non-git jobs
7. ✅ Graceful handling of errors (missing git, large repos, etc.)
