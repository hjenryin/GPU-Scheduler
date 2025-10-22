import sqlite3
import json
import os
from typing import List, Optional

from scheduler.storage.backend import StorageBackend
from scheduler.core.models import Job, Node
from scheduler.core.utils import ensure_dir_exists


class SQLiteBackend(StorageBackend):
    """SQLite storage backend"""

    def __init__(self, db_path: str):
        """
        Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = os.path.expanduser(db_path)

        # Ensure parent directory exists
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir:
            ensure_dir_exists(parent_dir)

        # Connect to database
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name

        # Initialize schema
        self._init_schema()

    def _init_schema(self):
        """
        Initialize database schema.
        Creates tables if they don't exist.
        """
        cursor = self.conn.cursor()

        # Jobs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        ''')

        # Nodes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_name TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        ''')

        self.conn.commit()

    def save_job(self, job: Job):
        """Save job to storage"""
        cursor = self.conn.cursor()
        job_data = json.dumps(job.to_dict())

        cursor.execute('''
            INSERT OR REPLACE INTO jobs (job_id, data)
            VALUES (?, ?)
        ''', (job.job_id, job_data))

        self.conn.commit()

    def load_job(self, job_id: str) -> Optional[Job]:
        """Load job from storage"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data FROM jobs WHERE job_id = ?', (job_id,))
        row = cursor.fetchone()

        if row:
            job_data = json.loads(row['data'])
            return Job.from_dict(job_data)
        return None

    def load_all_jobs(self) -> List[Job]:
        """Load all jobs from storage"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data FROM jobs')
        rows = cursor.fetchall()

        jobs = []
        for row in rows:
            job_data = json.loads(row['data'])
            jobs.append(Job.from_dict(job_data))

        return jobs

    def delete_job(self, job_id: str):
        """Delete job from storage"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
        self.conn.commit()

    def save_node(self, node: Node):
        """Save node to storage"""
        cursor = self.conn.cursor()
        node_data = json.dumps(node.to_dict())

        cursor.execute('''
            INSERT OR REPLACE INTO nodes (node_name, data)
            VALUES (?, ?)
        ''', (node.node_name, node_data))

        self.conn.commit()

    def load_node(self, node_name: str) -> Optional[Node]:
        """Load node from storage"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data FROM nodes WHERE node_name = ?', (node_name,))
        row = cursor.fetchone()

        if row:
            node_data = json.loads(row['data'])
            return Node.from_dict(node_data)
        return None

    def load_all_nodes(self) -> List[Node]:
        """Load all nodes from storage"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT data FROM nodes')
        rows = cursor.fetchall()

        nodes = []
        for row in rows:
            node_data = json.loads(row['data'])
            nodes.append(Node.from_dict(node_data))

        return nodes

    def close(self):
        """Close storage backend and cleanup resources"""
        if self.conn:
            self.conn.close()
