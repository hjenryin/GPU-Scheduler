"""Git-based snapshot management for job isolation using shadow repository"""

import os
import subprocess
import logging
import shutil
from typing import Optional, List, Set
from pathlib import Path

from scheduler.core.config import Config

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
    
    # Default file size thresholds (in bytes)
    DEFAULT_MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
    
    # Extensions that should always be included
    ALWAYS_INCLUDE_EXTENSIONS = {
        '.py', '.sh', '.yaml', '.yml', '.json', '.txt', '.md',
        '.toml', '.ini', '.cfg', '.conf', '.env'
    }
    
    # Patterns to always exclude
    EXCLUDE_PATTERNS = {
        '__pycache__', '.pytest_cache', '.mypy_cache', '.tox',
        '.egg-info', '.eggs', 'build', 'dist', '.git',
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
        
        # Shadow repository location
        self.shadow_repo_path = os.path.expanduser('~/.scheduler/shadow_repo')
        
        # Ensure shadow repo exists and is initialized
        self._ensure_shadow_repo()
        
        logger.debug(f"GitSnapshotManager initialized with shadow repo at {self.shadow_repo_path}")
    
    def _ensure_shadow_repo(self):
        """Ensure the shadow git repository exists and is initialized"""
        # Check if it's already a git repo
        git_dir = os.path.join(self.shadow_repo_path, '.git')
        if os.path.exists(git_dir):
            logger.debug(f"Shadow repo already initialized at {self.shadow_repo_path}")
            return
        
        # Create directory if needed
        if not os.path.exists(self.shadow_repo_path):
            os.makedirs(self.shadow_repo_path, exist_ok=True)
        
        try:
            # Initialize git repo
            subprocess.run(
                ['git', 'init'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            # Configure git
            subprocess.run(
                ['git', 'config', 'user.email', 'scheduler@localhost'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            subprocess.run(
                ['git', 'config', 'user.name', 'GPU Scheduler'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            
            # Create initial commit
            readme_path = os.path.join(self.shadow_repo_path, 'README.md')
            with open(readme_path, 'w') as f:
                f.write('# GPU Scheduler Shadow Repository\n\n')
                f.write('This repository contains snapshots of job submissions.\n')
            
            subprocess.run(
                ['git', 'add', 'README.md'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=True
            )
            subprocess.run(
                ['git', 'commit', '-m', 'Initial commit'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=True
            )
            
            logger.info(f"Initialized shadow git repository at {self.shadow_repo_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize shadow repository: {e}")
            raise
    
    def _should_include_file(self, file_path: str, working_dir: str) -> bool:
        """Determine if a file should be included in the snapshot
        
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
            
            # Check file extension - always include certain extensions
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.ALWAYS_INCLUDE_EXTENSIONS:
                return True
            
            # Check file size
            try:
                file_size = os.path.getsize(file_path)
                if file_size > self.DEFAULT_MAX_FILE_SIZE:
                    logger.debug(f"Excluding large file {rel_path} ({file_size} bytes)")
                    return False
            except OSError:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Error checking file {file_path}: {e}")
            return False
    
    def _collect_files_to_snapshot(self, working_dir: str) -> List[str]:
        """Collect list of files to include in snapshot
        
        Args:
            working_dir: Working directory to scan
            
        Returns:
            List of relative file paths to include
        """
        files_to_include = []
        
        try:
            for root, dirs, files in os.walk(working_dir):
                # Filter out excluded directories
                dirs[:] = [d for d in dirs if not any(pattern in d for pattern in self.EXCLUDE_PATTERNS)]
                
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
        """Create a git snapshot of the working directory in the shadow repository
        
        This creates a snapshot by:
        1. Creating a new branch in the shadow repo for this job
        2. Copying selected files from working_dir to shadow repo
        3. Committing the files
        4. Returning the commit SHA as the snapshot reference
        
        Args:
            job_id: Unique job identifier
            working_dir: Working directory to snapshot
            
        Returns:
            Snapshot reference (commit SHA) or None on error
        """
        try:
            branch_name = f"job-{job_id}"
            
            # Get current branch to return to
            result = subprocess.run(
                ['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=True
            )
            original_branch = result.stdout.strip()
            
            # Create and checkout new branch
            subprocess.run(
                ['git', 'checkout', '-b', branch_name],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=True
            )
            
            # Clear the shadow repo (except .git)
            for item in os.listdir(self.shadow_repo_path):
                if item != '.git':
                    item_path = os.path.join(self.shadow_repo_path, item)
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
            
            # Collect and copy files
            files_to_snapshot = self._collect_files_to_snapshot(working_dir)
            
            if not files_to_snapshot:
                logger.warning(f"No files to snapshot for job {job_id}")
                # Return to original branch
                subprocess.run(['git', 'checkout', original_branch], 
                             cwd=self.shadow_repo_path, 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=10)
                return None
            
            # Copy files maintaining directory structure
            for rel_path in files_to_snapshot:
                src = os.path.join(working_dir, rel_path)
                dst = os.path.join(self.shadow_repo_path, rel_path)
                
                # Create parent directories
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                
                # Copy file
                shutil.copy2(src, dst)
            
            # Add all files to git
            subprocess.run(
                ['git', 'add', '-A'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=True
            )
            
            # Commit with job info
            commit_message = f"Snapshot for job {job_id}\n\nSource: {working_dir}\nFiles: {len(files_to_snapshot)}"
            subprocess.run(
                ['git', 'commit', '-m', commit_message],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=True
            )
            
            # Get the commit SHA
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.shadow_repo_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=True
            )
            commit_sha = result.stdout.strip()
            
            # Return to original branch
            subprocess.run(
                ['git', 'checkout', original_branch],
                cwd=self.shadow_repo_path,
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
    
    def restore_snapshot(self, job_id: str, snapshot_ref: str, target_dir: str) -> bool:
        """Restore files from snapshot to a target directory using git worktree
        
        This creates a git worktree from the snapshot, providing an isolated
        working directory for the job execution.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference (commit SHA) from create_snapshot()
            target_dir: Target directory to create worktree in
            
        Returns:
            True if successful, False otherwise
        """
        if not snapshot_ref:
            logger.debug(f"No snapshot to restore for job {job_id}")
            return False
        
        try:
            # Create worktree from the snapshot
            subprocess.run(
                ['git', 'worktree', 'add', target_dir, snapshot_ref],
                cwd=self.shadow_repo_path,
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
    
    def cleanup_snapshot(self, job_id: str, snapshot_ref: str, worktree_dir: Optional[str] = None) -> None:
        """Clean up snapshot after job completion
        
        This removes the git worktree and optionally the branch.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference to clean up
            worktree_dir: Path to worktree directory to remove (if any)
        """
        try:
            # Remove worktree if specified
            if worktree_dir and os.path.exists(worktree_dir):
                try:
                    subprocess.run(
                        ['git', 'worktree', 'remove', worktree_dir, '--force'],
                        cwd=self.shadow_repo_path,
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
            # subprocess.run(['git', 'branch', '-D', branch_name], ...)
            
            logger.debug(f"Cleanup completed for job {job_id}")
            
        except Exception as e:
            logger.warning(f"Error during cleanup for job {job_id}: {e}")
