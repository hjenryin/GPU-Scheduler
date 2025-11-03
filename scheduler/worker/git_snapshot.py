"""Git-based snapshot management for job isolation using shadow repository"""

import os
import subprocess
import logging
from typing import Optional, List, Set, Dict, Tuple
import fnmatch
from pathlib import Path

from scheduler.core import Config
from scheduler.core import (
    DEFAULT_SNAPSHOT_MAX_FILE_SIZE,
    DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER,
    DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS,
    DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS,
    DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS
)

logger = logging.getLogger(__name__)


class GitSnapshotManager:
    """Manages git-based snapshots for job isolation using a shadow repository
    
    This class implements a shadow git repository approach where:
    - A separate git repository is maintained by the scheduler
    - Files are carefully selected based on size and configuration
    - Each job gets its own branch in the shadow repo
    - Jobs execute in isolated git worktrees
    
    File inclusion can be controlled via:
    - .scheduler_snapshot_ignore: Files to exclude (same format as .gitignore)
    - .scheduler_snapshot_include: Files to always include (bypasses all filters)
    
    This approach provides complete isolation from the user's workflow while
    being disk-efficient through git's delta compression.
    """
    
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

        # Load file extension and exclusion patterns (can be overridden by config)
        self.always_include_extensions = getattr(config, 'snapshot_always_include_extensions', DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS.copy())
        self.exclude_patterns = getattr(config, 'snapshot_exclude_patterns', DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS.copy())

        logger.debug(f"GitSnapshotManager initialized (max_file_size={self.max_file_size}, "
                    f"max_files_per_folder={self.max_files_per_folder})")

    def _git_base_args(self, workspace_root: str, git_dir: str) -> List[str]:
        """Return base git command args that inject a per-invocation safe.directory.

        We use `-c safe.directory=...` so git does not block operations due to
        dubious ownership checks. This is applied only to git invocations that
        operate on the shadow repository/work-tree for the scheduler and is
        supplied per-invocation (not persisted to global config).
        """
        return ['git', '-c', f'safe.directory={workspace_root}', f'--git-dir={git_dir}', f'--work-tree={workspace_root}']

    def _parse_scheduler_snapshot_ignore(self, working_dir: str) -> Set[str]:
        """Parse .scheduler_snapshot_ignore file in working directory

        The .scheduler_snapshot_ignore file uses the same format as .gitignore:
        - One pattern per line
        - Lines starting with # are comments
        - Empty lines are ignored
        - Patterns can be:
          - Directory names (e.g., 'wandb')
          - File patterns (e.g., '*.safetensors')
          - Path patterns (e.g., 'data/**/*.npy')

        Args:
            working_dir: The working directory to search for .scheduler_snapshot_ignore

        Returns:
            Set of patterns to exclude, empty set if file doesn't exist
        """
        ignore_file = os.path.join(working_dir, '.scheduler_snapshot_ignore')
        patterns = set()

        if not os.path.exists(ignore_file):
            logger.debug(f"No .scheduler_snapshot_ignore found in {working_dir}")
            return patterns

        try:
            with open(ignore_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    patterns.add(line)

            logger.info(f"Loaded {len(patterns)} patterns from .scheduler_snapshot_ignore")
            logger.debug(f"Patterns: {patterns}")

        except Exception as e:
            logger.warning(f"Failed to read .scheduler_snapshot_ignore: {e}")

        return patterns
    
    def _parse_scheduler_snapshot_include(self, working_dir: str) -> Set[str]:
        """Parse .scheduler_snapshot_include file in working directory

        The .scheduler_snapshot_include file uses the same format as .gitignore:
        - One pattern per line
        - Lines starting with # are comments
        - Empty lines are ignored
        - Patterns can be:
          - Specific file paths (e.g., 'data/model.pkl')
          - File patterns (e.g., '*.safetensors')
          - Directory patterns (e.g., 'models/**')

        Files matching these patterns will be included in snapshots regardless of:
        - Size limits
        - File type restrictions
        - Git exclude patterns

        Args:
            working_dir: The working directory to search for .scheduler_snapshot_include

        Returns:
            Set of patterns to always include, empty set if file doesn't exist
        """
        include_file = os.path.join(working_dir, '.scheduler_snapshot_include')
        patterns = set()

        if not os.path.exists(include_file):
            logger.debug(f"No .scheduler_snapshot_include found in {working_dir}")
            return patterns

        try:
            with open(include_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    patterns.add(line)

            logger.info(f"Loaded {len(patterns)} patterns from .scheduler_snapshot_include")
            logger.debug(f"Include patterns: {patterns}")

        except Exception as e:
            logger.warning(f"Failed to read .scheduler_snapshot_include: {e}")

        return patterns
    
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
    
    def _setup_git_exclude(self, working_dir: str):
        """Set up .scheduler-git/info/exclude with default patterns and .scheduler_snapshot_ignore

        Git's info/exclude file allows per-repo excludes without affecting .gitignore.
        We write our default patterns plus any user patterns from .scheduler_snapshot_ignore.

        Args:
            working_dir: The working directory containing the shadow repo
        """
        shadow_git_dir = self._get_shadow_repo_path(working_dir)
        info_dir = os.path.join(shadow_git_dir, 'info')
        exclude_file = os.path.join(info_dir, 'exclude')

        # Ensure info directory exists
        os.makedirs(info_dir, exist_ok=True)

        # Merge default patterns with user patterns
        user_patterns = self._parse_scheduler_snapshot_ignore(working_dir)
        all_patterns = self.exclude_patterns | user_patterns

        # Write to info/exclude
        try:
            with open(exclude_file, 'w') as f:
                f.write("# Scheduler snapshot exclude patterns\n")
                f.write("# Auto-generated - do not edit manually\n\n")

                f.write("# Default exclude patterns:\n")
                for pattern in sorted(self.exclude_patterns):
                    f.write(f"{pattern}\n")

                if user_patterns:
                    f.write("\n# From .scheduler_snapshot_ignore:\n")
                    for pattern in sorted(user_patterns):
                        f.write(f"{pattern}\n")

            logger.debug(f"Updated {exclude_file} with {len(all_patterns)} patterns")

        except Exception as e:
            logger.warning(f"Failed to write git exclude file: {e}")

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
            # Update exclude file even if repo exists (in case .scheduler_snapshot_ignore changed)
            self._setup_git_exclude(working_dir)
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

            # Set up git exclude patterns
            self._setup_git_exclude(working_dir)
            
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
        """Determine if a file should be included in the snapshot based on size limits

        Note: Exclude patterns are now handled by git via .scheduler-git/info/exclude.
        This method only checks file size limits.

        Args:
            file_path: Absolute path to the file
            working_dir: Working directory base path

        Returns:
            True if file should be included, False otherwise
        """
        try:
            # Get relative path for logging
            rel_path = os.path.relpath(file_path, working_dir)

            # Check file extension
            ext = os.path.splitext(file_path)[1].lower()

            # Check file size with data type-specific limits
            try:
                file_size = os.path.getsize(file_path)

                # Determine size limit for this file
                if ext in self.data_type_size_limits:
                    # Use data type-specific limit
                    size_limit = self.data_type_size_limits[ext]
                elif ext in self.always_include_extensions:
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

        Uses git ls-files to get all untracked/unignored files, automatically
        respecting .scheduler-git/info/exclude patterns. Additionally includes
        files specified in .scheduler_snapshot_include regardless of size/type limits.

        Args:
            working_dir: Working directory to scan

        Returns:
            List of relative file paths to include
        """
        files_to_include = set()  # Use set to avoid duplicates
        git_dir = self._get_shadow_repo_path(working_dir)

        # First, collect files from .scheduler_snapshot_include (bypass all filters)
        include_patterns = self._parse_scheduler_snapshot_include(working_dir)
        if include_patterns:
            logger.debug(f"Processing {len(include_patterns)} include patterns")
            
            for pattern in include_patterns:
                try:
                    # Convert gitignore-style patterns to glob patterns
                    # Handle ** for recursive matching
                    if '**' in pattern:
                        glob_pattern = pattern
                    else:
                        # For non-recursive patterns, search from working directory
                        glob_pattern = pattern
                    
                    # Use glob to find matching files
                    import glob
                    matches = glob.glob(os.path.join(working_dir, glob_pattern), recursive=True)
                    
                    for match in matches:
                        if os.path.isfile(match):
                            # Get relative path
                            rel_path = os.path.relpath(match, working_dir)
                            files_to_include.add(rel_path)
                            logger.debug(f"Included file from pattern '{pattern}': {rel_path}")
                
                except Exception as e:
                    logger.warning(f"Error processing include pattern '{pattern}': {e}")

        # Now collect files using git ls-files (with normal filtering)
        try:
            # Use git ls-files to get all files, excluding those in info/exclude
            # --others: show untracked files
            # We intentionally do NOT pass --exclude-standard here because
            # workspace .gitignore should not control the scheduler snapshot.
            # Instead we list all untracked files and apply scheduler-only
            # excludes (from DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS and
            # .scheduler_snapshot_ignore) in Python below.
            cmd = self._git_base_args(working_dir, git_dir) + ['ls-files', '--others']
            result = subprocess.run(
                cmd,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=True
            )

            git_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
            logger.debug(f"git ls-files found {len(git_files)} unfiltered untracked files")

            # Apply scheduler-only exclude patterns (combine defaults + user)
            user_patterns = self._parse_scheduler_snapshot_ignore(working_dir)
            combined_excludes = set(self.exclude_patterns) | set(user_patterns)

            def _matches_exclude(rel_path: str, patterns: Set[str]) -> bool:
                # Try matching with fnmatch against the relative path and
                # the basename. Also treat simple directory names as substring
                # matches to cover common ignore patterns.
                for pat in patterns:
                    if not pat:
                        continue
                    # Normalize pattern to use forward slashes
                    p = pat.replace('\\', '/')
                    if fnmatch.fnmatch(rel_path, p):
                        return True
                    if fnmatch.fnmatch(os.path.basename(rel_path), p):
                        return True
                    # If pattern looks like a directory name or simple token,
                    # check whether it's a path segment in rel_path
                    if '/' not in p and p in rel_path:
                        return True
                return False

            # Filter git_files according to scheduler excludes and already-included files
            filtered_git_files: List[str] = []
            for rel_path in git_files:
                if not rel_path:
                    continue
                # If explicitly included by .scheduler_snapshot_include, keep it
                if rel_path in files_to_include:
                    continue
                # Skip files that match scheduler-only excludes
                if _matches_exclude(rel_path, combined_excludes):
                    logger.debug(f"Excluding {rel_path} due to scheduler exclude patterns")
                    continue
                filtered_git_files.append(rel_path)

            logger.debug(f"After scheduler filtering {len(filtered_git_files)} files remain from git ls-files")

            # Apply size limits and folder limits to git files
            folder_file_counts: Dict[str, int] = {}

            # Count files per folder (only for git files, not included files)
            for rel_path in git_files:
                file_path = os.path.join(working_dir, rel_path)
                folder = os.path.dirname(file_path)
                folder_file_counts[folder] = folder_file_counts.get(folder, 0) + 1

            # Filter git files by size and folder limits
            for rel_path in filtered_git_files:
                # Skip if already included (no need to check again)
                if rel_path in files_to_include:
                    continue

                file_path = os.path.join(working_dir, rel_path)
                folder = os.path.dirname(file_path)

                # Check folder file limit
                if folder_file_counts.get(folder, 0) > self.max_files_per_folder:
                    logger.warning(f"Skipping folder {os.path.relpath(folder, working_dir)} "
                                 f"with {folder_file_counts[folder]} files (limit: {self.max_files_per_folder})")
                    continue

                # Check file size limits
                if self._should_include_file(file_path, working_dir):
                    files_to_include.add(rel_path)

        except subprocess.CalledProcessError as e:
            logger.error(f"git ls-files failed: {e.stderr}")
        except Exception as e:
            logger.error(f"Error collecting files from {working_dir}: {e}")

        final_files = list(files_to_include)
        logger.debug(f"Collected {len(final_files)} files to snapshot from {working_dir}")
        return final_files
    
    def _find_workspace_root(self, path: str) -> str:
        """Find the workspace root by searching for .git or .scheduler-git
        
        Searches upward from the given path to find:
        1. A .git directory (user's git repository)
        2. A .scheduler-git directory (our shadow repository)
        
        If neither is found, returns the original path.
        
        Args:
            path: Starting directory path
            
        Returns:
            Path to workspace root
        """
        current = os.path.abspath(path)
        
        # Search upward until we find .git or .scheduler-git or reach root
        while True:
            # Check for .git directory (user's repo)
            git_dir = os.path.join(current, '.git')
            if os.path.exists(git_dir):
                logger.info(f"Found .git directory at {current}")
                return current
            
            # Check for .scheduler-git directory (our shadow repo)
            scheduler_git_dir = os.path.join(current, '.scheduler-git')
            if os.path.exists(scheduler_git_dir):
                logger.info(f"Found .scheduler-git directory at {current}")
                return current
            
            # Move to parent directory
            parent = os.path.dirname(current)
            
            # Stop at filesystem root
            if parent == current:
                # No git repo found, use original path
                logger.debug(f"No .git or .scheduler-git found, using {path} as workspace root")
                return os.path.abspath(path)
            
            current = parent
    
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
    
    def create_snapshot(self, job_id: str, working_dir: str) -> Optional[Tuple[str, str]]:
        """Create a git snapshot of the working directory using the shadow repository
        
        This creates a snapshot by:
        1. Finding the workspace root (by searching for .git or .scheduler-git)
        2. Ensuring shadow repo exists (workspace_root/.scheduler-git as git dir)
        3. Collecting files to snapshot:
           - Files from .scheduler_snapshot_include (bypasses all filters)
           - Other files respecting size limits and exclude patterns
        4. Using git --git-dir and --work-tree to add files directly from workspace_root
        5. Creating a commit without checking out (using git write-tree and commit-tree)
        6. Creating a branch pointing to the commit
        7. Returning the commit SHA and workspace root
        
        Args:
            job_id: Unique job identifier
            working_dir: Working directory where job was submitted from
            
        Returns:
            Tuple of (snapshot_ref, workspace_root) or None on error
            - snapshot_ref: commit SHA in shadow repo
            - workspace_root: path to workspace root where snapshot was created
        """
        try:
            # Find the workspace root (search for .git or .scheduler-git)
            workspace_root = self._find_workspace_root(working_dir)
            logger.info(f"Using workspace root: {workspace_root} for job {job_id}")
            
            # Ensure shadow repo exists for this workspace
            self._ensure_shadow_repo(workspace_root)
            git_dir = self._get_shadow_repo_path(workspace_root)  # This IS the git dir
            
            branch_name = f"job-{job_id}"
            
            # Collect files to snapshot from workspace root
            files_to_snapshot = self._collect_files_to_snapshot(workspace_root)

            if not files_to_snapshot:
                logger.warning(f"No files to snapshot for job {job_id}")
                return None

            # Calculate total size and log progress information
            total_size = 0
            for rel_path in files_to_snapshot:
                try:
                    file_path = os.path.join(workspace_root, rel_path)
                    total_size += os.path.getsize(file_path)
                except OSError:
                    pass

            total_size_mb = total_size / (1024 * 1024)
            logger.info(f"Creating snapshot for job {job_id}: {len(files_to_snapshot)} files, "
                       f"{total_size_mb:.2f} MB total")

            # Warn if snapshot is large
            if len(files_to_snapshot) > 1000:
                logger.warning(f"Large snapshot detected: {len(files_to_snapshot)} files. "
                             f"Consider creating a .scheduler_snapshot_ignore file to exclude unnecessary files.")

            if total_size_mb > 100:
                logger.warning(f"Large snapshot detected: {total_size_mb:.2f} MB. "
                             f"Consider creating a .scheduler_snapshot_ignore file to exclude large data files.")

            # Reset index to clear any previous state
            cmd = self._git_base_args(workspace_root, git_dir) + ['reset']
            subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )

            # Add selected files in batches to avoid argument length limits
            # Batch size of 1000 files per git add call for efficiency
            BATCH_SIZE = 1000
            for i in range(0, len(files_to_snapshot), BATCH_SIZE):
                batch = files_to_snapshot[i:i + BATCH_SIZE]
                # Add all files in this batch with a single git add call
                # If batch fails, the entire snapshot creation fails (no fallback)
                cmd = self._git_base_args(workspace_root, git_dir) + ['add', '-f', '--'] + batch
                subprocess.run(
                    cmd,
                    cwd=workspace_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,  # Increased timeout for batch operations
                    check=True
                )
                logger.debug(f"Added batch of {len(batch)} files to git index")
            
            # Write tree (creates tree object from index)
            cmd = self._git_base_args(workspace_root, git_dir) + ['write-tree']
            result = subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            tree_sha = result.stdout.strip()
            
            # Get parent commit (if any)
            parent_args = []
            cmd = self._git_base_args(workspace_root, git_dir) + ['rev-parse', 'HEAD']
            result = subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                parent_sha = result.stdout.strip()
                parent_args = ['-p', parent_sha]
            
            # Create commit object
            # Note: commit message includes the original working_dir for reference
            commit_message = f"Snapshot for job {job_id}\n\nWorkspace: {workspace_root}\nSubmitted from: {working_dir}\nFiles: {len(files_to_snapshot)}"
            cmd = self._git_base_args(workspace_root, git_dir) + ['commit-tree', tree_sha] + parent_args + ['-m', commit_message]
            result = subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            commit_sha = result.stdout.strip()
            
            # Create/update branch to point to this commit
            cmd = self._git_base_args(workspace_root, git_dir) + ['branch', '-f', branch_name, commit_sha]
            subprocess.run(
                cmd,
                cwd=workspace_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            logger.info(f"Created snapshot {commit_sha} for job {job_id} on branch {branch_name} ({len(files_to_snapshot)} files)")
            return (commit_sha, workspace_root)
            
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
            cmd = self._git_base_args(working_dir, git_dir) + ['worktree', 'add', target_dir, snapshot_ref]
            subprocess.run(
                cmd,
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
                    cmd = self._git_base_args(working_dir, git_dir) + ['worktree', 'remove', worktree_dir, '--force']
                    subprocess.run(
                        cmd,
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
