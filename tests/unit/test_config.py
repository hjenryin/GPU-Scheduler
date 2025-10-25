"""Unit tests for configuration module"""
import pytest
import os
import tempfile
import yaml

from scheduler.core.config import Config, HeadConfig, WorkerConfig, StorageConfig, ClientConfig, load_config, save_config, init_config
from scheduler.core.exceptions import ValidationException, PermissionDeniedException


class TestConfig:
    """Tests for Config class"""

    def test_config_defaults(self):
        """Test default configuration values"""
        config = Config()

        # Check top-level
        assert config.address is None

        # Check head config defaults
        assert config.head.port == 8265
        assert config.head.heartbeat_timeout == 60
        assert config.head.scheduling_interval == 5

        # Check worker config defaults
        assert config.worker.temp_dir == "~/.scheduler/tmp"
        assert config.worker.log_dir == "~/.scheduler/logs"
        assert config.worker.work_dir == "~/.scheduler/work"
        assert config.worker.gpu_poll_interval == 10
        assert config.worker.gpu_util_threshold == 10.0
        assert config.worker.gpu_mem_threshold == 10.0
        assert config.worker.gpu_stable_time == 30
        assert config.worker.job_startup_grace == 120

        # Check storage config defaults
        assert config.storage.backend == "file"
        assert config.storage.data_dir == "~/.scheduler/data"

    def test_config_custom_values(self):
        """Test custom configuration values"""
        config = Config(
            address="192.168.1.100:9000",
            head=HeadConfig(port=9000, heartbeat_timeout=120, graceful_shutdown_timeout=90),
            worker=WorkerConfig(gpu_util_threshold=15.0, gpu_poll_interval=5)
        )

        assert config.address == "192.168.1.100:9000"
        assert config.head.port == 9000
        assert config.head.heartbeat_timeout == 120
        assert config.head.graceful_shutdown_timeout == 90
        assert config.worker.gpu_util_threshold == 15.0
        assert config.worker.gpu_poll_interval == 5

        # Defaults should still be present
        assert config.head.scheduling_interval == 5
        assert config.worker.gpu_mem_threshold == 10.0

    def test_config_from_dict_flat(self):
        """Test creating config from flat dictionary"""
        config_dict = {
            'address': '192.168.1.100:9000',
            'head': {
                'port': 9000,
                'heartbeat_timeout': 120
            },
            'worker': {
                'gpu_util_threshold': 15.0
            }
        }

        config = Config.from_dict(config_dict)

        assert config.address == '192.168.1.100:9000'
        assert config.head.port == 9000
        assert config.head.heartbeat_timeout == 120
        assert config.worker.gpu_util_threshold == 15.0

        # Defaults should be filled in
        assert config.head.scheduling_interval == 5
        assert config.worker.gpu_poll_interval == 10

    def test_config_from_dict_legacy_keys(self):
        """Test creating config from dict with legacy key names"""
        config_dict = {
            'head_node': {  # legacy name
                'port': 9000,
                'heartbeat_timeout': 120
            },
            'node': {  # legacy name for worker
                'gpu_poll_interval': 5
            }
        }

        config = Config.from_dict(config_dict)

        # Should map legacy keys correctly
        assert config.head.port == 9000
        assert config.head.heartbeat_timeout == 120
        assert config.worker.gpu_poll_interval == 5

    def test_config_from_dict_filters_invalid_keys(self):
        """Test that from_dict filters out invalid keys"""
        config_dict = {
            'address': 'localhost:8265',
            'head': {
                'port': 9000,
                'invalid_key': 'should be ignored'
            },
            'extra_key': 'should be ignored'
        }

        config = Config.from_dict(config_dict)

        assert config.address == 'localhost:8265'
        assert config.head.port == 9000
        assert not hasattr(config.head, 'invalid_key')
        assert not hasattr(config, 'extra_key')

    def test_config_to_dict(self):
        """Test converting config to dictionary"""
        config = Config(
            address="localhost:9000",
            head=HeadConfig(port=9000)
        )

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict['address'] == 'localhost:9000'
        assert config_dict['head']['port'] == 9000
        assert config_dict['head']['heartbeat_timeout'] == 60  # default
        assert 'worker' in config_dict
        assert 'storage' in config_dict
        assert 'client' in config_dict

    def test_config_immutable(self):
        """Test that config is immutable (frozen)"""
        config = Config()

        with pytest.raises(Exception):  # dataclass FrozenInstanceError
            config.address = "new_address"

        with pytest.raises(Exception):
            config.head.port = 9999


class TestLoadConfig:
    """Tests for load_config function"""

    def test_load_config_nonexistent(self):
        """Test loading non-existent config returns defaults"""
        with tempfile.NamedTemporaryFile(delete=True) as f:
            config_path = f.name + "_nonexistent.yaml"

        config = load_config(config_path)

        assert isinstance(config, Config)
        assert config.head.port == 8265  # Default value

    def test_load_config_valid_yaml(self):
        """Test loading valid YAML config"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({
                'address': '192.168.1.100:9000',
                'head': {
                    'port': 9000,
                    'heartbeat_timeout': 45
                },
                'worker': {
                    'gpu_util_threshold': 20.0
                }
            }, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.address == '192.168.1.100:9000'
            assert config.head.port == 9000
            assert config.head.heartbeat_timeout == 45
            assert config.worker.gpu_util_threshold == 20.0
        finally:
            os.unlink(config_path)

    def test_load_config_empty_file(self):
        """Test loading empty config file returns defaults"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("")
            config_path = f.name

        try:
            config = load_config(config_path)

            assert isinstance(config, Config)
            assert config.head.port == 8265  # Default value
        finally:
            os.unlink(config_path)

    def test_load_config_invalid_yaml(self):
        """Test loading invalid YAML raises exception"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("invalid: yaml: content: [")
            config_path = f.name

        try:
            with pytest.raises(ValidationException):
                load_config(config_path)
        finally:
            os.unlink(config_path)

    def test_load_config_partial_config(self):
        """Test loading partial config merges with defaults"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'head': {'port': 9000}}, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            # Custom value
            assert config.head.port == 9000
            # Default values should still be present
            assert config.head.heartbeat_timeout == 60
            assert config.worker.gpu_util_threshold == 10.0
        finally:
            os.unlink(config_path)


class TestSaveConfig:
    """Tests for save_config function"""

    def test_save_config_new_file(self):
        """Test saving config to new file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config = Config(
                address="localhost:9000",
                head=HeadConfig(port=9000, heartbeat_timeout=45)
            )

            save_config(config, config_path)

            assert os.path.exists(config_path)

            # Load and verify
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            assert data['address'] == 'localhost:9000'
            assert data['head']['port'] == 9000
            assert data['head']['heartbeat_timeout'] == 45

    def test_save_config_overwrite(self):
        """Test saving config overwrites existing file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")

            # Save first config
            config1 = Config(head=HeadConfig(port=9000))
            save_config(config1, config_path)

            # Save second config
            config2 = Config(head=HeadConfig(port=9999))
            save_config(config2, config_path)

            # Load and verify second config
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            assert data['head']['port'] == 9999

    def test_save_config_creates_directory(self):
        """Test saving config creates parent directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "subdir", "config.yaml")
            config = Config(head=HeadConfig(port=9000))

            save_config(config, config_path)

            assert os.path.exists(config_path)

    def test_save_config_invalid_path(self):
        """Test saving to invalid path raises exception"""
        config = Config()

        # Try to save to root directory (likely permission denied)
        if os.name != 'nt':  # Unix-like systems
            with pytest.raises(PermissionDeniedException):
                save_config(config, "/root/config.yaml")


class TestInitConfig:
    """Tests for init_config function"""

    def test_init_config_creates_default(self):
        """Test init_config creates default config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")

            init_config(config_path)

            assert os.path.exists(config_path)

            # Load and verify defaults
            config = load_config(config_path)
            assert config.head.port == 8265
            assert config.head.heartbeat_timeout == 60

    def test_init_config_file_exists(self):
        """Test init_config raises error if file exists"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("existing: config")
            config_path = f.name

        try:
            with pytest.raises(FileExistsError):
                init_config(config_path)
        finally:
            os.unlink(config_path)
