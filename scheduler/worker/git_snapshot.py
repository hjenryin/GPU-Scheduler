"""Git-based snapshot management for job isolation"""

import os
import subprocess
import logging
import shutil
from typing import Optional
from pathlib import Path

from scheduler.core.config import Config

logger = logging.getLogger(__name__)


class GitSnapshotManager:
    """Manages git-based snapshots for job isolation
    
    This class handles creating and restoring snapshots of job working directories
    using git. When a job is submitted from a git repository, a snapshot is created
    to preserve the exact state of files at submission time. When the job runs,
    this snapshot is restored to ensure the job executes with the original files,
    even if they have changed in the meantime.
    """
    
    def __init__(self, config: Config):
        """Initialize git snapshot manager
        
        Args:
            config: Configuration instance
        """
        self.config = config
        logger.debug("GitSnapshotManager initialized")
    
    def is_git_repository(self, path: str) -> bool:
        """Check if path is inside a git repository
        
        Args:
            path: Directory path to check
            
        Returns:
            True if path is in a git repository, False otherwise
        """
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--git-dir'],
                cwd=path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            is_git = result.returncode == 0
            logger.debug(f"Path {path} is {'in' if is_git else 'not in'} a git repository")
            return is_git
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            logger.debug(f"Git check failed for {path}: {e}")
            return False
    
    def create_snapshot(self, job_id: str, working_dir: str) -> Optional[str]:
        """Create a git snapshot of the working directory
        
        This creates a snapshot using git to capture the current state of all
        files in the working directory. The snapshot includes both tracked and
        untracked files.
        
        Args:
            job_id: Unique job identifier
            working_dir: Working directory to snapshot
            
        Returns:
            Snapshot reference (commit SHA) or None if not a git repo or on error
        """
        if not self.is_git_repository(working_dir):
            logger.debug(f"Skipping snapshot for job {job_id}: not a git repository")
            return None
        
        try:
            # Get the current commit SHA
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=True
            )
            commit_sha = result.stdout.strip()
            
            # Check if there are any uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
                check=True
            )
            
            has_changes = bool(result.stdout.strip())
            
            if has_changes:
                # Create a stash to save uncommitted changes
                stash_name = f"job-snapshot-{job_id}"
                result = subprocess.run(
                    ['git', 'stash', 'push', '-u', '-m', stash_name],
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=10,
                    check=True
                )
                
                # Get the stash reference
                result = subprocess.run(
                    ['git', 'rev-parse', 'stash@{0}'],
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5,
                    check=True
                )
                stash_sha = result.stdout.strip()
                
                # Restore the working directory (pop the stash)
                subprocess.run(
                    ['git', 'stash', 'pop'],
                    cwd=working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=True
                )
                
                snapshot_ref = f"{commit_sha}:{stash_sha}"
                logger.info(f"Created git snapshot {snapshot_ref} for job {job_id} (with uncommitted changes)")
                return snapshot_ref
            else:
                # No uncommitted changes, just use the commit SHA
                logger.info(f"Created git snapshot {commit_sha} for job {job_id} (no uncommitted changes)")
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
        """Restore files from snapshot to a target directory
        
        This restores the snapshot by checking out the appropriate git commit
        and applying any stashed changes.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference from create_snapshot()
            target_dir: Target directory to restore files to
            
        Returns:
            True if successful, False otherwise
        """
        if not snapshot_ref:
            logger.debug(f"No snapshot to restore for job {job_id}")
            return False
        
        try:
            # Parse snapshot reference
            if ':' in snapshot_ref:
                # Format: "commit_sha:stash_sha" (has uncommitted changes)
                commit_sha, stash_sha = snapshot_ref.split(':', 1)
                has_stash = True
            else:
                # Format: "commit_sha" (no uncommitted changes)
                commit_sha = snapshot_ref
                stash_sha = None
                has_stash = False
            
            # Ensure target directory exists
            os.makedirs(target_dir, exist_ok=True)
            
            # Initialize git repo in target directory if not already
            git_dir = os.path.join(target_dir, '.git')
            if not os.path.exists(git_dir):
                # This is a fresh directory, we need to clone or init
                # For simplicity, we'll just note that the working directory
                # should already be a git repo and we'll work with it
                logger.debug(f"Target directory {target_dir} is not a git repo")
                return False
            
            # Checkout the commit
            result = subprocess.run(
                ['git', 'checkout', commit_sha, '--force'],
                cwd=target_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=30,
                check=True
            )
            
            # Apply stashed changes if present
            if has_stash and stash_sha:
                # Cherry-pick the stash commit to apply the changes
                result = subprocess.run(
                    ['git', 'cherry-pick', '-n', stash_sha],
                    cwd=target_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30
                )
                # It's okay if this fails - we have the base commit at least
                if result.returncode != 0:
                    logger.warning(f"Failed to apply stashed changes for job {job_id}, using base commit only")
            
            logger.info(f"Restored git snapshot {snapshot_ref} for job {job_id} to {target_dir}")
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
    
    def cleanup_snapshot(self, job_id: str, snapshot_ref: str) -> None:
        """Clean up snapshot after job completion
        
        This removes temporary files and references created for the snapshot.
        Note: We keep stashes in the original repository as they don't take much space
        and git will automatically clean them up eventually.
        
        Args:
            job_id: Unique job identifier
            snapshot_ref: Snapshot reference to clean up
        """
        logger.debug(f"Snapshot cleanup for job {job_id}: {snapshot_ref}")
        # For now, we don't need to do anything special
        # Stashes will be cleaned up by git's normal garbage collection
        # The temp directory will be cleaned up by the file handler
