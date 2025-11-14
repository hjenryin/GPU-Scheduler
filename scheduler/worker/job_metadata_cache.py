"""Persistent cache for job metadata on worker nodes"""

import os
import json
import logging
from typing import Optional, Dict
from threading import Lock

logger = logging.getLogger(__name__)


class JobMetadataCache:
    """
    Persistent cache for storing job metadata on worker nodes.

    This cache stores job_id -> snapshot_working_dir mappings so that
    when jobs are purged, the worker can find and clean up git snapshots
    even after the job has been deleted from the head node's database.
    """

    def __init__(self, cache_dir: str):
        """
        Initialize job metadata cache.

        Args:
            cache_dir: Directory to store cache file
        """
        self.cache_dir = os.path.expanduser(cache_dir)
        self.cache_file = os.path.join(self.cache_dir, 'job_metadata_cache.json')
        self.lock = Lock()

        # Ensure cache directory exists
        os.makedirs(self.cache_dir, exist_ok=True)

        # Load existing cache
        self._cache: Dict[str, str] = self._load_cache()

        logger.debug(f"JobMetadataCache initialized with {len(self._cache)} entries")

    def _load_cache(self) -> Dict[str, str]:
        """Load cache from disk."""
        if not os.path.exists(self.cache_file):
            return {}

        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            logger.debug(f"Loaded {len(cache)} entries from cache file")
            return cache
        except Exception as e:
            logger.warning(f"Failed to load cache file: {e}, starting with empty cache")
            return {}

    def _save_cache(self):
        """Save cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self._cache, f, indent=2)
            logger.debug(f"Saved {len(self._cache)} entries to cache file")
        except Exception as e:
            logger.error(f"Failed to save cache file: {e}")

    def store_job_metadata(self, job_id: str, snapshot_working_dir: Optional[str]):
        """
        Store job metadata.

        Args:
            job_id: Job ID
            snapshot_working_dir: Workspace root where snapshot was created (can be None)
        """
        if snapshot_working_dir is None:
            # No snapshot, nothing to cache
            return

        with self.lock:
            self._cache[job_id] = snapshot_working_dir
            self._save_cache()
            logger.debug(f"Stored metadata for job {job_id}: {snapshot_working_dir}")

    def get_snapshot_working_dir(self, job_id: str) -> Optional[str]:
        """
        Get snapshot working directory for a job.

        Args:
            job_id: Job ID

        Returns:
            Snapshot working directory, or None if not found
        """
        with self.lock:
            return self._cache.get(job_id)

    def remove_job_metadata(self, job_id: str):
        """
        Remove job metadata from cache.

        Args:
            job_id: Job ID
        """
        with self.lock:
            if job_id in self._cache:
                del self._cache[job_id]
                self._save_cache()
                logger.debug(f"Removed metadata for job {job_id}")

    def cleanup_stale_entries(self, active_job_ids: set):
        """
        Remove entries for jobs that are no longer tracked.

        This can be called periodically to clean up the cache.

        Args:
            active_job_ids: Set of job IDs that should be kept
        """
        with self.lock:
            initial_count = len(self._cache)
            self._cache = {job_id: path for job_id, path in self._cache.items()
                          if job_id in active_job_ids}
            removed_count = initial_count - len(self._cache)

            if removed_count > 0:
                self._save_cache()
                logger.info(f"Cleaned up {removed_count} stale cache entries")
