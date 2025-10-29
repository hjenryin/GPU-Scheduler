"""Git-based snapshot management for job isolation using shadow repository"""

import os
import subprocess
import logging
from typing import Optional, List, Set, Dict
from pathlib import Path

from scheduler.core import Config
from scheduler.core.constants import (
    DEFAULT_SNAPSHOT_MAX_FILE_SIZE,
    DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER,
    DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS
)

logger = logging.getLogger(__name__)


class GitSnapshotManager:
    """Manages git-based snapshots for job isolation using a shadow repository
    
    This class implements a shadow git repository approach where:
    - A separate git repository is maintained by the scheduler
    - Files are carefully selected based on size and configuration
    - Each job gets its own branch in the shadow repo
    - Jobs execute in isolated git worktrees
    
    This approach provides complete isolation from the user's workflow while
    being disk-efficient through git's delta compression.
    """
    
    # Extensions that should always be included
    ALWAYS_INCLUDE_EXTENSIONS = {
        '.py', '.sh', '.yaml', '.yml', '.json', '.txt', '.md',
        '.toml', '.ini', '.cfg', '.conf', '.env'
    }
    
    # Patterns to always exclude
    EXCLUDE_PATTERNS = {
        '__pycache__', '.pytest_cache', '.mypy_cache', '.tox',
        '.egg-info', '.eggs', 'build', 'dist', '.git', '.scheduler-git',
        '*.pyc', '*.pyo', '*.pyd', '.so', '*.dylib',
        '.coverage', 'htmlcov', '.DS_Store', '*.swp', '*.swo',
        '.vscode', '.idea', '*.log'
    }
    
    def __init__(self, config: Config):
        """Initialize git snapshot manager
        
        Args:
            config: Configuration instance
        """
        self.config = config
        
        # Load configuration values with defaults from constants
        self.max_file_size = getattr(config, 'snapshot_max_file_size', DEFAULT_SNAPSHOT_MAX_FILE_SIZE)
        self.max_files_per_folder = getattr(config, 'snapshot_max_files_per_folder', DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER)
        
        # Load data type size limits (can be overridden by config)
        self.data_type_size_limits = getattr(config, 'snapshot_data_type_limits', DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS.copy())
        
        logger.debug(f"GitSnapshotManager initialized (max_file_size={self.max_file_size}, "
                    f"max_files_per_folder={self.max_files_per_folder})")
    
    def _get_shadow_repo_path(self, working_dir: str) -> str:
        """Get the shadow repository path for a given working directory
        
        Note: The shadow repo IS a .git directory at the working directory root.
        We use .scheduler-git as the git directory name (not a folder containing .git).
        This .scheduler-git directory directly contains branches/, objects/, refs/, etc.
        
        Args:
            working_dir: The working directory path
            
        Returns:
            Path to the shadow git directory (which IS the git dir, not a parent folder)
        """
        # .scheduler-git IS the git directory (contains branches, objects, etc.)
        return os.path.join(working_dir, '.scheduler-git')
    
    def _ensure_shadow_repo(self, working_dir: str):
        """Ensure the shadow git repository exists and is initialized
        
        This initializes a git repository where .scheduler-git IS the git directory.
        Unlike normal git repos, we don't have .git - instead .scheduler-git serves
        as the git directory directly.
        
        Args:
            working_dir: The working directory that needs a shadow repo
        """
        shadow_git_dir = self._get_shadow_repo_path(working_dir)
        
        # Check if it's already initialized (check for HEAD file)
        head_file = os.path.join(shadow_git_dir, 'HEAD')
        if os.path.exists(head_file):
            logger.debug(f"Shadow repo already initialized at {shadow_git_dir}")
            return
        
        # Create git directory if needed
        if not os.path.exists(shadow_git_dir):
            os.makedirs(shadow_git_dir, exist_ok=True)
        
        try:
            # Initialize git repo with --separate-git-dir equivalent
            # We use git init with --git-dir to create repo structure directly in .scheduler-git
            subprocess.run(
                ['git', 'init', '--bare'],
                cwd=shadow_git_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            # Configure git
            subprocess.run(
                ['git', f'--git-dir={shadow_git_dir}', 'config', 'user.email', 'scheduler@localhost'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            subprocess.run(
                ['git', f'--git-dir={shadow_git_dir}', 'config', 'user.name', 'GPU Scheduler'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            
            # Set bare to false so we can use it with --work-tree
            subprocess.run(
                ['git', f'--git-dir={shadow_git_dir}', 'config', 'core.bare', 'false'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            
            logger.info(f"Initialized shadow git repository at {shadow_git_dir}")
            
        except Exception as e:
            logger.error(f"Failed to initialize shadow repository: {e}")
            raise
    
    def _should_include_file(self, file_path: str, working_dir: str) -> bool:
        """Determine if a file should be included in the snapshot
        
        Uses configurable size limits and data type-specific overrides.
        
        Args:
            file_path: Absolute path to the file
            working_dir: Working directory base path
            
        Returns:
            True if file should be included, False otherwise
        """
        try:
            # Get relative path
            rel_path = os.path.relpath(file_path, working_dir)
            
            # Check exclude patterns
            for pattern in self.EXCLUDE_PATTERNS:
                if pattern in rel_path or Path(rel_path).match(pattern):
                    return False
            
            # Check file extension
            ext = os.path.splitext(file_path)[1].lower()
            
            # Check file size with data type-specific limits
            try:
                file_size = os.path.getsize(file_path)
                
                # Determine size limit for this file
                if ext in self.data_type_size_limits:
                    # Use data type-specific limit
                    size_limit = self.data_type_size_limits[ext]
                elif ext in self.ALWAYS_INCLUDE_EXTENSIONS:
                    # Always include these extensions (they're typically small)
                    return True
                else:
                    # Use default size limit
                    size_limit = self.max_file_size
                
                if file_size > size_limit:
                    logger.debug(f"Excluding file {rel_path} ({file_size} bytes > {size_limit} limit)")
                    return False
                    
            except OSError:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking file {file_path}: {e}")
            return False
    
    def _collect_files_to_snapshot(self, working_dir: str) -> List[str]:
        """Collect list of files to include in snapshot
        
        Applies folder file count limits to prevent snapshotting folders with too many files.
        
        Args:
            working_dir: Working directory to scan
            
        Returns:
            List of relative file paths to include
        """
        files_to_include = []
        
        try:
            # First pass: count files per folder
            folder_file_counts: Dict[str, int] = {}
            
            for root, dirs, files in os.walk(working_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.EXCLUDE_PATTERNS)]
                
                # Count files in this folder (not including subdirectories)
                file_count = len([f for f in files if os.path.isfile(os.path.join(root, f))])
                folder_file_counts[root] = file_count
            
            # Second pass: collect files, excluding folders with too many files
            for root, dirs, files in os.walk(working_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.EXCLUDE_PATTERNS)]
                
                # Skip folders with too many files
                if folder_file_counts.get(root, 0) > self.max_files_per_folder:
                    logger.warning(f"Skipping folder {os.path.relpath(root, working_dir)} "
                                 f"with {folder_file_counts[root]} files (limit: {self.max_files_per_folder})")
                    dirs[:] = []  # Don't descend into subdirectories either
                    continue
                
                for file in files:
                    file_path = os.path.join(root, file)
                    if self._should_include_file(file_path, working_dir):
                        rel_path = os.path.relpath(file_path, working_dir)
                        files_to_include.append(rel_path)
            
            logger.debug(f"Collected {len(files_to_include)} files to snapshot from {working_dir}")
            return files_to_include
            
        except Exception as e:
            logger.error(f"Error collecting files from {working_dir}: {e}")
            return []
    
    def is_git_repository(self, path: str) -> bool:
        """Check if path is inside a git repository
        
        Note: This now checks if we should create a snapshot, not if user has git.
        We always create snapshots in our shadow repo.
        
        Args:
            path: Directory path to check
            
        Returns:
            True if we should create a snapshot (always True now)
        """
        # We always create snapshots in the shadow repo
        return True
    
    def create_snapshot(self, job_id: str, working_dir: str) -> Optional[str]:
        """Create a git snapshot of the working directory using the shadow repository
        
        This creates a snapshot by:
        1. Ensuring shadow repo exists (working_dir/.scheduler-git as git dir)
        2. Using git --git-dir and --work-tree to add files directly from working_dir
        3. Creating a commit without checking out (using git write-tree and commit-tree)
        4. Creating a branch pointing to the commit
        5. Returning the commit SHA as the snapshot reference
        
        Args:
            job_id: Unique job identifier
            working_dir: Working directory to snapshot
            
        Returns:
            Snapshot reference (commit SHA) or None on error
        """
        try:
            # Ensure shadow repo exists for this workspace
            self._ensure_shadow_repo(working_dir)
            git_dir = self._get_shadow_repo_path(working_dir)  # This IS the git dir
            
            branch_name = f"job-{job_id}"
            
            # Collect files to snapshot
            files_to_snapshot = self._collect_files_to_snapshot(working_dir)
            
            if not files_to_snapshot:
                logger.warning(f"No files to snapshot for job {job_id}")
                return None
            
            # Reset index to clear any previous state
            subprocess.run(
                ['git', f'--git-dir={git_dir}', f'--work-tree={working_dir}', 'reset'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            # Add selected files
            for rel_path in files_to_snapshot:
                try:
                    subprocess.run(
                        ['git', f'--git-dir={git_dir}', f'--work-tree={working_dir}', 'add', '--', rel_path],
                        cwd=working_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        timeout=5,
                        check=True
                    )
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Failed to add file {rel_path}: {e.stderr}")
            
            # Write tree (creates tree object from index)
            result = subprocess.run(
                ['git', f'--git-dir={git_dir}', 'write-tree'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            tree_sha = result.stdout.strip()
            
            # Get parent commit (if any)
            parent_args = []
            result = subprocess.run(
                ['git', f'--git-dir={git_dir}', 'rev-parse', 'HEAD'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                parent_sha = result.stdout.strip()
                parent_args = ['-p', parent_sha]
            
            # Create commit object
            commit_message = f"Snapshot for job {job_id}\n\nSource: {working_dir}\nFiles: {len(files_to_snapshot)}"
            result = subprocess.run(
                ['git', f'--git-dir={git_dir}', 'commit-tree', tree_sha] + parent_args + ['-m', commit_message],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            commit_sha = result.stdout.strip()
            
            # Create/update branch to point to this commit
            subprocess.run(
                ['git', f'--git-dir={git_dir}', 'branch', '-f', branch_name, commit_sha],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            logger.info(f"Created snapshot {commit_sha} for job {job_id} on branch {branch_name} ({len(files_to_snapshot)} files)")
            return commit_sha
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Git command timed out while creating snapshot for job {job_id}")
            return None
        except subprocess.CalledProcessError as e:
            logger.warning(f"Git command failed while creating snapshot for job {job_id}: {e.stderr}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error creating snapshot for job {job_id}: {e}")
            return None
    
    def restore_snapshot(self, job_id: str, snapshot_ref: str, working_dir: str, target_dir: str) -> bool:
        """Restore files from snapshot to a target directory using git worktree
        
        This creates a git worktree from the snapshot, providing an isolated
        working directory for the job execution.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference (commit SHA) from create_snapshot()
            working_dir: Original working directory (to find the shadow repo)
            target_dir: Target directory to create worktree in
            
        Returns:
            True if successful, False otherwise
        """
        if not snapshot_ref:
            logger.debug(f"No snapshot to restore for job {job_id}")
            return False
        
        try:
            git_dir = self._get_shadow_repo_path(working_dir)  # This IS the git dir
            
            if not os.path.exists(git_dir):
                logger.error(f"Shadow repo not found at {git_dir}")
                return False
            
            # Create worktree from the snapshot
            subprocess.run(
                ['git', f'--git-dir={git_dir}', 'worktree', 'add', target_dir, snapshot_ref],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
                check=True
            )
            
            logger.info(f"Restored snapshot {snapshot_ref} for job {job_id} to {target_dir}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"Git command timed out while restoring snapshot for job {job_id}")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed while restoring snapshot for job {job_id}: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error restoring snapshot for job {job_id}: {e}")
            return False
    
    def cleanup_snapshot(self, job_id: str, snapshot_ref: str, working_dir: str, worktree_dir: Optional[str] = None) -> None:
        """Clean up snapshot after job completion
        
        This removes the git worktree and optionally the branch.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference to clean up
            working_dir: Original working directory (to find the shadow repo)
            worktree_dir: Path to worktree directory to remove (if any)
        """
        try:
            git_dir = self._get_shadow_repo_path(working_dir)  # This IS the git dir
            
            # Remove worktree if specified
            if worktree_dir and os.path.exists(worktree_dir):
                try:
                    subprocess.run(
                        ['git', f'--git-dir={git_dir}', 'worktree', 'remove', worktree_dir, '--force'],
                        cwd=working_dir,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=30,
                        check=True
                    )
                    logger.debug(f"Removed worktree {worktree_dir} for job {job_id}")
                except Exception as e:
                    logger.warning(f"Failed to remove worktree {worktree_dir}: {e}")
            
            # Optionally prune old branches (keep for now for debugging)
            # branch_name = f"job-{job_id}"
            # subprocess.run(['git', f'--git-dir={git_dir}', 'branch', '-D', branch_name], ...)
            
            logger.debug(f"Cleanup completed for job {job_id}")
            
        except Exception as e:
            logger.warning(f"Error during cleanup for job {job_id}: {e}")
