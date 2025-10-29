# Per-Workspace Shadow Git Repository Implementation

## Overview

This document describes the implementation of per-workspace shadow git repositories for job configuration snapshots. Each workspace gets its own shadow repository that tracks files in-place using git's `--git-dir` and `--work-tree` capabilities.

## Design Philosophy

### Transparent Background Operation

The scheduler operates independently of the user's workflow. Users never interact with the shadow repository directly - it's purely an internal mechanism for the scheduler.

### Per-Workspace Shadow Repositories

Instead of a unified shadow repository, each workspace maintains its own:

- **Location**: `{workspace}/.scheduler-git/`
- **Independence**: One shadow repo per workspace for better isolation
- **Control**: Scheduler has full control over these repositories
- **No User Impact**: Never modifies user's working directory or their git state
- **Colocated**: Shadow repos live alongside the workspaces they track

### Direct Git Operations (No File Copying)

The system uses git's `--git-dir` and `--work-tree` flags to track files in-place:

- **No Duplication**: Files remain in user's working directory
- **Direct Tracking**: Git commits files from their original location
- **Efficient**: No copying or moving of files
- **Clean**: Shadow repo only contains git metadata and one README.md

### Smart File Selection

The system only snapshots files that are likely needed for reproducibility:

- **Size-based filtering**: Exclude files over 20MB by default
- **Pattern-based filtering**: Always exclude `__pycache__`, `.git`, `.scheduler-git`, build artifacts
- **Extension-based inclusion**: Always include source code, configs, scripts
- **Configurable**: Thresholds and patterns can be adjusted

## User Experience

### Job Submission

When a user submits a job, the scheduler:

1. Ensures shadow repo exists at `{workspace}/.scheduler-git/`
2. Collects relevant files from the working directory based on filters
3. Uses `git --git-dir` and `--work-tree` to add/commit files directly from workspace
4. Creates a commit in a job-specific branch
5. Returns the commit SHA as the snapshot reference
6. User continues working normally (no changes to their files)

### Job Execution

When the job runs, the scheduler:

1. Creates a git worktree from the snapshot commit
2. Executes the job in the isolated worktree
3. Job sees only the files that were captured at submission time
4. Cleans up the worktree after completion

## Technical Implementation

### Shadow Repository Structure

Per workspace:
```
/path/to/workspace/
├── .scheduler-git/          # Shadow repo (auto-created)
│   ├── .git/                # Git metadata
│   └── README.md            # Initial marker
├── your_code.py             # User's files (tracked in-place)
├── config.yaml              # User's files (tracked in-place)
└── ...                      # User's files (tracked in-place)
```

Each job gets its own branch:
- Branch name: `job-{job_id}`
- Isolated from other jobs
- Can be inspected or cleaned up independently

### File Selection Algorithm

**Inclusion Rules:**
1. **Always include** if extension in: `.py`, `.sh`, `.yaml`, `.yml`, `.json`, `.txt`, `.md`, `.toml`, `.ini`, `.cfg`, `.conf`, `.env`
2. **Include if small** (< 20MB) and not in exclusion list
3. **Exclude** if in patterns: `__pycache__`, `.pytest_cache`, `.git`, `.scheduler-git`, `*.pyc`, `*.log`, `.coverage`, etc.

**Example:**
```python
# Included: train.py, config.yaml, requirements.txt
# Excluded: large_model.pth (>20MB), __pycache__/*, .git/, .scheduler-git/
```

### Git Operations

All git operations use `--git-dir` and `--work-tree` to track files in-place:

```bash
# Define paths
WORKSPACE=/path/to/workspace
SHADOW_GIT=$WORKSPACE/.scheduler-git/.git

# Create snapshot (NO file copying - tracks in-place)
git --git-dir=$SHADOW_GIT --work-tree=$WORKSPACE checkout -b job-abc123
git --git-dir=$SHADOW_GIT --work-tree=$WORKSPACE add train.py config.yaml
git --git-dir=$SHADOW_GIT --work-tree=$WORKSPACE commit -m "Snapshot for job abc123"

# Restore snapshot (via worktree)
git --git-dir=$SHADOW_GIT worktree add /tmp/job-abc123 job-abc123

# Cleanup
git --git-dir=$SHADOW_GIT worktree remove /tmp/job-abc123
```

**Key Points:**
- Files never leave the workspace directory
- Shadow repo only contains git metadata
- `--work-tree` tells git where the actual files are
- `--git-dir` tells git where to store metadata

### Integration Points

#### JobManager.submit_job()
```python
def submit_job(self, ...):
    # Existing job creation code
    job = Job(...)
    
    # NEW: Create snapshot in per-workspace shadow repo
    git_manager = GitSnapshotManager(self.config)
    if git_manager.is_git_repository(working_dir):  # Always True now
        snapshot_ref = git_manager.create_snapshot(job_id, working_dir)
        if snapshot_ref:
            job.snapshot_ref = snapshot_ref
            job.snapshot_working_dir = working_dir
```

#### JobExecutor.execute_job()
```python
def execute_job(self, job: Job, gpu_ids: List[int]):
    # NEW: Restore snapshot to worktree if available
    if job.snapshot_ref and job.snapshot_working_dir:
        worktree_dir = self.file_handler.get_job_snapshot_dir(job.job_id)
        if git_manager.restore_snapshot(
            job.job_id, job.snapshot_ref, job.snapshot_working_dir, worktree_dir
        ):
            # Execute job in worktree
            actual_working_dir = worktree_dir
        else:
            # Fallback to original directory
            actual_working_dir = job.working_dir
    
    # Rest of execution code...
```

## Key Classes

### GitSnapshotManager

**Location**: `scheduler/worker/git_snapshot.py`

**Key Methods:**

```python
class GitSnapshotManager:
    def __init__(self, config: Config):
        """Initialize with shadow repo at ~/.scheduler/shadow_repo/"""
        
    def is_git_repository(self, path: str) -> bool:
        """Always returns True (we use shadow repo)"""
        
    def create_snapshot(self, job_id: str, working_dir: str) -> Optional[str]:
        """
        Create snapshot in shadow repo:
        1. Checkout new branch job-{job_id}
        2. Copy selected files from working_dir
        3. Commit files
        4. Return commit SHA
        """
        
    def restore_snapshot(self, job_id: str, snapshot_ref: str, target_dir: str) -> bool:
        """
        Restore snapshot via git worktree:
        1. Create worktree at target_dir
        2. Checkout snapshot_ref
        3. Return True if successful
        """
        
    def cleanup_snapshot(self, job_id: str, snapshot_ref: str, worktree_dir: str):
        """Remove worktree after job completion"""
```

### Job Model Changes

**Removed**: `versioned_script_path` field (no longer needed with full repo checkout)

**Retained**: 
- `snapshot_ref`: Commit SHA in shadow repo
- `snapshot_working_dir`: Original working directory

## File Size Thresholds

| File Type | Threshold | Rationale |
|-----------|-----------|-----------|
| Source Code (.py, .sh) | Always include | Essential for reproducibility |
| Configs (.yaml, .json) | Always include | Essential for reproducibility |
| Generic files | 20 MB | Balance between completeness and disk usage |
| Build artifacts | Always exclude | Not needed, can be regenerated |
| Git metadata | Always exclude | Shadow repo is separate |

## Testing Strategy

### Unit Tests (21 tests)

**TestGitSnapshotManager**: Initialization and shadow repo setup
**TestIsGitRepository**: Always returns True
**TestFileSelection**: Size and pattern-based filtering
**TestCreateSnapshot**: Snapshot creation in shadow repo
**TestRestoreSnapshot**: Worktree-based restoration
**TestCleanupSnapshot**: Worktree cleanup
**TestIntegration**: Complete workflow

### Integration Tests (6 tests)

- Job submission creates snapshot (git and non-git directories)
- Snapshot includes correct files
- Job serialization preserves snapshot fields
- Backward compatibility with old jobs
- Error resilience

## Comparison: Old vs New Approach

| Aspect | Old (Stash) | New (Shadow Repo) |
|--------|-------------|-------------------|
| User's git | Modified (stash) | Never touched |
| Git requirement | User must have git | Not required |
| File selection | All files | Smart filtering |
| Storage | User's repo | Shadow repo |
| Isolation | Checkout + stash | Git worktree |
| Versioned script | Separate field | Part of snapshot |

## Benefits of Shadow Repository Approach

1. **No User Impact**: Never modifies user's git or working directory
2. **Works Everywhere**: Not limited to git repositories
3. **Disk Efficient**: Only includes relevant files, uses git delta compression
4. **Complete Isolation**: Each job in its own worktree
5. **Flexible**: Easy to add configuration for file patterns/sizes
6. **Inspectable**: Jobs are git branches, easy to inspect with git tools
7. **Cleanable**: Can prune old job branches to reclaim space

## Future Enhancements

### Configuration Options

Add to `~/.scheduler/config.yaml`:

```yaml
snapshot:
  enabled: true
  max_file_size_mb: 20
  include_extensions:
    - .py
    - .yaml
    - .json
  exclude_patterns:
    - __pycache__
    - "*.pyc"
    - .git
  shadow_repo_path: ~/.scheduler/shadow_repo
```

### Advanced Features

1. **Snapshot Compression**: Compress snapshots for older jobs
2. **Retention Policy**: Auto-delete snapshots older than N days
3. **Snapshot Diff**: Show what changed between submission and current state
4. **Selective Restoration**: Restore only specific files from snapshot
5. **Snapshot Sharing**: Share snapshots between similar jobs (git already does this via delta compression)

## Security Considerations

1. **File Access**: Shadow repo respects file permissions
2. **Sensitive Files**: Should add patterns to exclude secrets (`.env`, `credentials.*`)
3. **Disk Usage**: Monitor shadow repo size, implement cleanup policies
4. **Git Isolation**: Shadow repo completely isolated from user's git

## Success Criteria

✅ Jobs submitted from any directory (git or not)
✅ Only relevant files captured in snapshot
✅ User's working directory never modified
✅ Jobs execute in isolated environments
✅ All tests passing (27/27)
✅ Backward compatible with jobs without snapshots
✅ No breaking changes to existing functionality

## Conclusion

The shadow git repository approach provides a robust, efficient, and non-invasive way to capture job configurations. By maintaining a separate repository under the scheduler's control, we achieve:

- Complete independence from user's workflow
- Smart file selection to manage disk usage
- Git's built-in efficiency for storage
- Easy inspection and cleanup
- Future extensibility

This design aligns with the principles from the complete ML Job Scheduler Design Document while being practical for implementation and maintenance.
