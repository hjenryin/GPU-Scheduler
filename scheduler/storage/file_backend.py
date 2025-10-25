import json
import os
from typing import List, Optional

from scheduler.storage.backend import StorageBackend
from scheduler.core.models import Job, Node
from scheduler.core.utils import ensure_dir_exists


class FileBackend(StorageBackend):
    """File-based storage backend (JSON)"""

    def __init__(self, storage_dir: str):
        """
        Initialize file backend.

        Args:
            storage_dir: Directory for storage files
        """
        self.storage_dir = os.path.expanduser(storage_dir)
        ensure_dir_exists(self.storage_dir)

        self.jobs_file = os.path.join(self.storage_dir, 'jobs.json')
        self.nodes_file = os.path.join(self.storage_dir, 'nodes.json')

        # Initialize files if they don't exist
        if not os.path.exists(self.jobs_file):
            self._write_json(self.jobs_file, {})
        if not os.path.exists(self.nodes_file):
            self._write_json(self.nodes_file, {})

    def _read_json(self, filepath: str) -> dict:
        """Read JSON from file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write_json(self, filepath: str, data: dict):
        """Write JSON to file."""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def save_job(self, job: Job):
        """Save job to storage"""
        jobs = self._read_json(self.jobs_file)
        jobs[job.job_id] = job.to_dict()
        self._write_json(self.jobs_file, jobs)

    def load_job(self, job_id: str) -> Optional[Job]:
        """Load job from storage"""
        jobs = self._read_json(self.jobs_file)
        job_data = jobs.get(job_id)
        if job_data:
            return Job.from_dict(job_data)
        return None

    def load_all_jobs(self) -> List[Job]:
        """Load all jobs from storage"""
        jobs = self._read_json(self.jobs_file)
        return [Job.from_dict(job_data) for job_data in jobs.values()]

    def delete_job(self, job_id: str):
        """Delete job from storage"""
        jobs = self._read_json(self.jobs_file)
        if job_id in jobs:
            del jobs[job_id]
            self._write_json(self.jobs_file, jobs)

    def save_node(self, node: Node):
        """Save node to storage"""
        nodes = self._read_json(self.nodes_file)
        nodes[node.node_name] = node.to_dict()
        self._write_json(self.nodes_file, nodes)

    def load_node(self, node_name: str) -> Optional[Node]:
        """Load node from storage"""
        nodes = self._read_json(self.nodes_file)
        node_data = nodes.get(node_name)
        if node_data:
            return Node.from_dict(node_data)
        return None

    def load_all_nodes(self) -> List[Node]:
        """Load all nodes from storage"""
        nodes = self._read_json(self.nodes_file)
        return [Node.from_dict(node_data) for node_data in nodes.values()]

    def close(self):
        """Close storage backend and cleanup resources"""
        # File backend doesn't need explicit cleanup
        # All data is persisted to disk immediately
        pass
