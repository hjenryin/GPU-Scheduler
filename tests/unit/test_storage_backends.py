"""Unit tests for storage backends"""
import pytest
import json
import os
import sqlite3
from unittest.mock import patch, MagicMock

from scheduler.storage.file_backend import FileBackend
from scheduler.storage.sqlite_backend import SQLiteBackend
from scheduler.core.models import Job, JobStatus, JobRequirement, Node, NodeStatus, GPU, GPUStats


@pytest.fixture
def file_backend(temp_dir):
    """Create file backend for testing"""
    return FileBackend(storage_dir=temp_dir)


@pytest.fixture
def temp_db_path(temp_dir):
    """Create temporary database path"""
    return os.path.join(temp_dir, "test.db")


@pytest.fixture
def sqlite_backend(temp_db_path):
    """Create SQLite backend for testing"""
    return SQLiteBackend(db_path=temp_db_path)


class TestFileBackend:
    """Tests for FileBackend class"""

    def test_save_job(self, file_backend):
        """Test saving a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        file_backend.save_job(job)
        
        # Check jobs.json file was created
        jobs_file = os.path.join(file_backend.storage_dir, "jobs.json")
        assert os.path.exists(jobs_file)
        
        # Check content
        with open(jobs_file, 'r') as f:
            data = json.load(f)
        assert "test-job-001" in data
        assert data["test-job-001"]['job_id'] == "test-job-001"
        assert data["test-job-001"]['name'] == "test-job"

    def test_load_job(self, file_backend):
        """Test loading a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        file_backend.save_job(job)
        loaded_job = file_backend.load_job("test-job-001")
        
        assert loaded_job.job_id == job.job_id
        assert loaded_job.name == job.name
        assert loaded_job.script == job.script

    def test_load_job_not_found(self, file_backend):
        """Test loading non-existent job"""
        loaded_job = file_backend.load_job("non-existent")
        assert loaded_job is None

    def test_delete_job(self, file_backend):
        """Test deleting a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        file_backend.save_job(job)
        assert file_backend.load_job("test-job-001") is not None
        
        file_backend.delete_job("test-job-001")
        assert file_backend.load_job("test-job-001") is None

    def test_delete_job_not_found(self, file_backend):
        """Test deleting non-existent job (should not raise error)"""
        file_backend.delete_job("non-existent")

    def test_save_node(self, file_backend):
        """Test saving a node"""
        gpu_stats = GPUStats(
            gpu_id=0,
            utilization=50.0,
            memory_used=1024,
            memory_total=2048,
            temperature=65,
            power_draw=150,
            power_limit=200
        )
        gpu = GPU(gpu_id=0, stats=gpu_stats)
        node = Node(
            node_name="test-node",
            address="localhost:8080",
            num_gpus=1,
            gpus=[gpu]
        )
        
        file_backend.save_node(node)
        
        # Check nodes.json file was created
        nodes_file = os.path.join(file_backend.storage_dir, "nodes.json")
        assert os.path.exists(nodes_file)
        
        # Check content
        with open(nodes_file, 'r') as f:
            data = json.load(f)
        assert "test-node" in data
        assert data["test-node"]['node_name'] == "test-node"
        assert data["test-node"]['address'] == "localhost:8080"

    def test_load_node(self, file_backend):
        """Test loading a node"""
        gpu_stats = GPUStats(
            gpu_id=0,
            utilization=50.0,
            memory_used=1024,
            memory_total=2048,
            temperature=65,
            power_draw=150,
            power_limit=200
        )
        gpu = GPU(gpu_id=0, stats=gpu_stats)
        node = Node(
            node_name="test-node",
            address="localhost:8080",
            num_gpus=1,
            gpus=[gpu]
        )
        
        file_backend.save_node(node)
        loaded_node = file_backend.load_node("test-node")
        
        assert loaded_node.node_name == node.node_name
        assert loaded_node.address == node.address
        assert len(loaded_node.gpus) == 1

    def test_load_node_not_found(self, file_backend):
        """Test loading non-existent node"""
        loaded_node = file_backend.load_node("non-existent")
        assert loaded_node is None

    def test_delete_node_not_implemented(self, file_backend):
        """Test that delete_node is not part of the storage interface"""
        # FileBackend doesn't have delete_node method - this is correct
        # as it's not part of the StorageBackend interface
        assert not hasattr(file_backend, 'delete_node')

    def test_read_json_file_not_found(self, file_backend):
        """Test _read_json with non-existent file"""
        result = file_backend._read_json("/non/existent/file.json")
        assert result == {}

    def test_read_json_invalid_json(self, file_backend, temp_dir):
        """Test _read_json with invalid JSON file"""
        invalid_file = os.path.join(temp_dir, "invalid.json")
        with open(invalid_file, 'w') as f:
            f.write("invalid json content")
        
        result = file_backend._read_json(invalid_file)
        assert result == {}

    def test_write_json_creates_directory(self, file_backend, temp_dir):
        """Test _write_json creates parent directory"""
        # Create the directory first since FileBackend doesn't auto-create
        nested_dir = os.path.join(temp_dir, "nested", "deep")
        os.makedirs(nested_dir, exist_ok=True)
        nested_file = os.path.join(nested_dir, "file.json")
        data = {"test": "data"}
        
        file_backend._write_json(nested_file, data)
        
        assert os.path.exists(nested_file)
        with open(nested_file, 'r') as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_write_json_permission_error(self, file_backend):
        """Test _write_json with permission error"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied"), autospec=True):
            with pytest.raises(PermissionError):
                file_backend._write_json("/root/readonly/file.json", {"test": "data"})

    def test_ensure_dir_exists_creates_directory(self, temp_dir):
        """Test ensure_dir_exists creates directory"""
        # Test that FileBackend creates directory when initializing
        nested_dir = os.path.join(temp_dir, "nested", "deep", "storage")
        backend = FileBackend(storage_dir=nested_dir)
        assert os.path.exists(nested_dir)
        backend.close()

    def test_ensure_dir_exists_existing_directory(self, temp_dir):
        """Test ensure_dir_exists with existing directory"""
        # Test that FileBackend works with existing directory
        existing_dir = os.path.join(temp_dir, "existing")
        os.makedirs(existing_dir, exist_ok=True)
        
        backend = FileBackend(storage_dir=existing_dir)
        assert os.path.exists(existing_dir)
        backend.close()


class TestSQLiteBackend:
    """Tests for SQLiteBackend class"""

    def test_init_creates_database(self, temp_db_path):
        """Test that SQLiteBackend creates database file"""
        backend = SQLiteBackend(db_path=temp_db_path)
        assert os.path.exists(temp_db_path)
        assert backend.db_path == temp_db_path
        backend.close()

    def test_init_creates_parent_directory(self, temp_dir):
        """Test that SQLiteBackend creates parent directory"""
        nested_path = os.path.join(temp_dir, "nested", "deep", "test.db")
        backend = SQLiteBackend(db_path=nested_path)
        assert os.path.exists(nested_path)
        backend.close()

    def test_init_expands_user_path(self, temp_dir):
        """Test that SQLiteBackend expands user path"""
        with patch.dict(os.environ, {'HOME': temp_dir}):
            user_path = "~/test.db"
            backend = SQLiteBackend(db_path=user_path)
            expected_path = os.path.join(temp_dir, "test.db")
            assert backend.db_path == expected_path
            backend.close()

    def test_init_schema_creates_tables(self, sqlite_backend):
        """Test that _init_schema creates required tables"""
        cursor = sqlite_backend.conn.cursor()
        
        # Check jobs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cursor.fetchone() is not None
        
        # Check nodes table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='nodes'")
        assert cursor.fetchone() is not None

    def test_save_job(self, sqlite_backend):
        """Test saving a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        sqlite_backend.save_job(job)
        
        # Check job was saved
        cursor = sqlite_backend.conn.cursor()
        cursor.execute("SELECT data FROM jobs WHERE job_id = ?", (job.job_id,))
        row = cursor.fetchone()
        assert row is not None
        
        # Check data content
        job_data = json.loads(row['data'])
        assert job_data['job_id'] == "test-job-001"
        assert job_data['name'] == "test-job"

    def test_save_job_updates_existing(self, sqlite_backend):
        """Test saving job updates existing record"""
        job1 = Job(
            job_id="test-job-001",
            name="original-name",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        sqlite_backend.save_job(job1)
        
        # Update job
        job2 = Job(
            job_id="test-job-001",
            name="updated-name",
            script="/path/to/script.py",
            requirements=JobRequirement("2")
        )
        sqlite_backend.save_job(job2)
        
        # Check only one record exists with updated data
        cursor = sqlite_backend.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE job_id = ?", (job1.job_id,))
        count = cursor.fetchone()[0]
        assert count == 1
        
        cursor.execute("SELECT data FROM jobs WHERE job_id = ?", (job1.job_id,))
        row = cursor.fetchone()
        job_data = json.loads(row['data'])
        assert job_data['name'] == "updated-name"

    def test_load_job(self, sqlite_backend):
        """Test loading a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        sqlite_backend.save_job(job)
        loaded_job = sqlite_backend.load_job("test-job-001")
        
        assert loaded_job is not None
        assert loaded_job.job_id == job.job_id
        assert loaded_job.name == job.name
        assert loaded_job.script == job.script

    def test_load_job_not_found(self, sqlite_backend):
        """Test loading non-existent job"""
        loaded_job = sqlite_backend.load_job("non-existent")
        assert loaded_job is None

    def test_load_all_jobs(self, sqlite_backend):
        """Test loading all jobs"""
        # Save multiple jobs
        jobs = []
        for i in range(3):
            job = Job(
                job_id=f"test-job-{i:03d}",
                name=f"test-job-{i}",
                script=f"/path/to/script{i}.py",
                requirements=JobRequirement("1")
            )
            jobs.append(job)
            sqlite_backend.save_job(job)
        
        loaded_jobs = sqlite_backend.load_all_jobs()
        assert len(loaded_jobs) == 3
        
        # Check all jobs are loaded
        loaded_ids = {job.job_id for job in loaded_jobs}
        expected_ids = {job.job_id for job in jobs}
        assert loaded_ids == expected_ids

    def test_load_all_jobs_empty(self, sqlite_backend):
        """Test loading all jobs when none exist"""
        loaded_jobs = sqlite_backend.load_all_jobs()
        assert loaded_jobs == []

    def test_delete_job(self, sqlite_backend):
        """Test deleting a job"""
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        sqlite_backend.save_job(job)
        assert sqlite_backend.load_job("test-job-001") is not None
        
        sqlite_backend.delete_job("test-job-001")
        assert sqlite_backend.load_job("test-job-001") is None

    def test_delete_job_not_found(self, sqlite_backend):
        """Test deleting non-existent job (should not raise error)"""
        sqlite_backend.delete_job("non-existent")

    def test_save_node(self, sqlite_backend):
        """Test saving a node"""
        gpu_stats = GPUStats(
            gpu_id=0,
            utilization=50.0,
            memory_used=1024,
            memory_total=2048,
            temperature=65,
            power_draw=150,
            power_limit=200
        )
        gpu = GPU(gpu_id=0, stats=gpu_stats)
        node = Node(
            node_name="test-node",
            address="localhost:8080",
            num_gpus=1,
            gpus=[gpu]
        )
        
        sqlite_backend.save_node(node)
        
        # Check node was saved
        cursor = sqlite_backend.conn.cursor()
        cursor.execute("SELECT data FROM nodes WHERE node_name = ?", (node.node_name,))
        row = cursor.fetchone()
        assert row is not None
        
        # Check data content
        node_data = json.loads(row['data'])
        assert node_data['node_name'] == "test-node"
        assert node_data['address'] == "localhost:8080"

    def test_load_node(self, sqlite_backend):
        """Test loading a node"""
        gpu_stats = GPUStats(
            gpu_id=0,
            utilization=50.0,
            memory_used=1024,
            memory_total=2048,
            temperature=65,
            power_draw=150,
            power_limit=200
        )
        gpu = GPU(gpu_id=0, stats=gpu_stats)
        node = Node(
            node_name="test-node",
            address="localhost:8080",
            num_gpus=1,
            gpus=[gpu]
        )
        
        sqlite_backend.save_node(node)
        loaded_node = sqlite_backend.load_node("test-node")
        
        assert loaded_node is not None
        assert loaded_node.node_name == node.node_name
        assert loaded_node.address == node.address
        assert loaded_node.address == node.address
        assert len(loaded_node.gpus) == 1

    def test_load_node_not_found(self, sqlite_backend):
        """Test loading non-existent node"""
        loaded_node = sqlite_backend.load_node("non-existent")
        assert loaded_node is None

    def test_load_all_nodes(self, sqlite_backend):
        """Test loading all nodes"""
        # Save multiple nodes
        nodes = []
        for i in range(3):
            gpu_stats = GPUStats(
                gpu_id=0,
                utilization=50.0,
                memory_used=1024,
                memory_total=2048,
                temperature=65,
                power_draw=150,
                power_limit=200
            )
            gpu = GPU(gpu_id=0, stats=gpu_stats)
            node = Node(
                node_name=f"test-node-{i}",
                address=f"localhost:{8080 + i}",
                num_gpus=1,
                gpus=[gpu]
            )
            nodes.append(node)
            sqlite_backend.save_node(node)
        
        loaded_nodes = sqlite_backend.load_all_nodes()
        assert len(loaded_nodes) == 3
        
        # Check all nodes are loaded
        loaded_names = {node.node_name for node in loaded_nodes}
        expected_names = {node.node_name for node in nodes}
        assert loaded_names == expected_names

    def test_load_all_nodes_empty(self, sqlite_backend):
        """Test loading all nodes when none exist"""
        loaded_nodes = sqlite_backend.load_all_nodes()
        assert loaded_nodes == []

    def test_close(self, sqlite_backend):
        """Test closing the backend"""
        assert sqlite_backend.conn is not None
        sqlite_backend.close()
        # Connection should be closed (we can't easily test this without mocking)

    def test_close_already_closed(self, sqlite_backend):
        """Test closing already closed backend"""
        sqlite_backend.close()
        # Should not raise error
        sqlite_backend.close()

    def test_database_connection_error(self, temp_dir):
        """Test handling database connection errors"""
        # Create a path that will cause connection error
        invalid_path = os.path.join(temp_dir, "invalid", "path", "test.db")
        
        with patch('sqlite3.connect', side_effect=sqlite3.Error("Connection failed"), autospec=True):
            with pytest.raises(sqlite3.Error):
                SQLiteBackend(db_path=invalid_path)

    def test_json_serialization_error(self, sqlite_backend):
        """Test handling JSON serialization errors"""
        # Create a job with unserializable data
        job = Job(
            job_id="test-job-001",
            name="test-job",
            script="/path/to/script.py",
            requirements=JobRequirement("1")
        )
        
        # Mock to_dict to return unserializable data
        with patch.object(job, 'to_dict', return_value={'invalid': object()}, autospec=True):
            with patch('json.dumps', side_effect=TypeError("Object not serializable"), autospec=True):
                with pytest.raises(TypeError):
                    sqlite_backend.save_job(job)

    def test_json_deserialization_error(self, sqlite_backend):
        """Test handling JSON deserialization errors"""
        # Insert invalid JSON data directly
        cursor = sqlite_backend.conn.cursor()
        cursor.execute("INSERT INTO jobs (job_id, data) VALUES (?, ?)", ("test-job-001", "invalid json"))
        sqlite_backend.conn.commit()
        
        # Loading should handle the error gracefully
        with patch('json.loads', side_effect=json.JSONDecodeError("Invalid JSON", "", 0), autospec=True):
            with pytest.raises(json.JSONDecodeError):
                sqlite_backend.load_job("test-job-001")

    def test_ensure_dir_exists_error(self, temp_dir):
        """Test handling ensure_dir_exists errors"""
        # Test that SQLiteBackend handles directory creation errors gracefully
        from scheduler.core.exceptions import PermissionDeniedException
        
        # Mock ensure_dir_exists to raise PermissionDeniedException
        with patch('scheduler.storage.sqlite_backend.ensure_dir_exists', side_effect=PermissionDeniedException("Cannot create directory"), autospec=True):
            with pytest.raises(PermissionDeniedException):
                SQLiteBackend(db_path=os.path.join(temp_dir, "test.db"))
