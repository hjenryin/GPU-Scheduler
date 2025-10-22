"""Unit tests for configuration module"""
import pytest
import os
import tempfile
import yaml

from scheduler.core.config import Config, load_config, save_config, init_config
from scheduler.core.exceptions import ValidationException, PermissionDeniedException


class TestConfig:
    """Tests for Config class"""

    def test_config_defaults(self):
        """Test default configuration values"""
        config = Config()

        assert config.port == 8265
        assert config.heartbeat_timeout == 30
        assert config.scheduling_interval == 10
        assert config.gpu_poll_interval == 5
        assert config.gpu_util_threshold == 10.0
        assert config.gpu_mem_threshold == 10.0
        assert config.gpu_stable_time == 60
        assert config.job_startup_grace == 30

    def test_config_custom_values(self):
        """Test custom configuration values"""
        config = Config(
            port=9000,
            heartbeat_timeout=60,
            gpu_util_threshold=15.0
        )

        assert config.port == 9000
        assert config.heartbeat_timeout == 60
        assert config.gpu_util_threshold == 15.0

    def test_config_from_dict(self):
        """Test creating config from dictionary"""
        config_dict = {
            'port': 9000,
            'heartbeat_timeout': 60,
            'gpu_util_threshold': 15.0,
            'extra_key': 'should_be_ignored'  # Should be filtered out
        }

        config = Config.from_dict(config_dict)

        assert config.port == 9000
        assert config.heartbeat_timeout == 60
        assert config.gpu_util_threshold == 15.0
        # Extra key should not be in config
        assert not hasattr(config, 'extra_key')

    def test_config_to_dict(self):
        """Test converting config to dictionary"""
        config = Config(
            port=9000,
            heartbeat_timeout=60
        )

        config_dict = config.to_dict()

        assert isinstance(config_dict, dict)
        assert config_dict['port'] == 9000
        assert config_dict['heartbeat_timeout'] == 60


class TestLoadConfig:
    """Tests for load_config function"""

    def test_load_config_nonexistent(self):
        """Test loading non-existent config returns defaults"""
        with tempfile.NamedTemporaryFile(delete=True) as f:
            config_path = f.name + "_nonexistent.yaml"

        config = load_config(config_path)

        assert isinstance(config, Config)
        assert config.port == 8265  # Default value

    def test_load_config_valid_yaml(self):
        """Test loading valid YAML config"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({
                'port': 9000,
                'heartbeat_timeout': 45,
                'gpu_util_threshold': 20.0
            }, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            assert config.port == 9000
            assert config.heartbeat_timeout == 45
            assert config.gpu_util_threshold == 20.0
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
            assert config.port == 8265  # Default value
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
            yaml.safe_dump({'port': 9000}, f)
            config_path = f.name

        try:
            config = load_config(config_path)

            # Custom value
            assert config.port == 9000
            # Default values should still be present
            assert config.heartbeat_timeout == 30
            assert config.gpu_util_threshold == 10.0
        finally:
            os.unlink(config_path)


class TestSaveConfig:
    """Tests for save_config function"""

    def test_save_config_new_file(self):
        """Test saving config to new file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")
            config = Config(port=9000, heartbeat_timeout=45)

            save_config(config, config_path)

            assert os.path.exists(config_path)

            # Load and verify
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            assert data['port'] == 9000
            assert data['heartbeat_timeout'] == 45

    def test_save_config_overwrite(self):
        """Test saving config overwrites existing file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.yaml")

            # Save first config
            config1 = Config(port=9000)
            save_config(config1, config_path)

            # Save second config
            config2 = Config(port=9999)
            save_config(config2, config_path)

            # Load and verify second config
            with open(config_path, 'r') as f:
                data = yaml.safe_load(f)

            assert data['port'] == 9999

    def test_save_config_creates_directory(self):
        """Test saving config creates parent directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "subdir", "config.yaml")
            config = Config(port=9000)

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
            assert config.port == 8265
            assert config.heartbeat_timeout == 30

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
