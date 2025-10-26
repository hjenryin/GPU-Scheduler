"""Unit tests for CLI config command implementation"""
import pytest
from unittest.mock import patch, mock_open, Mock
import tempfile
import yaml
from io import StringIO

from scheduler.cli.config import config_command
from scheduler.core.config import Config, HeadConfig, WorkerConfig, StorageConfig, ClientConfig
from scheduler.core.exceptions import ValidationException


class TestConfigCommand:
    """Tests for config_command function"""

    def test_config_init(self):
        """Test config init command"""
        with patch('scheduler.cli.config.init_config') as mock_init, \
             patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='init')
            
            assert result == 0
            mock_init.assert_called_once()

    @patch('scheduler.cli.config.load_config')
    def test_config_show(self, mock_load_config):
        """Test config show command"""
        config = Config(
            address="localhost:8265",
            head=HeadConfig(port=8265),
            worker=WorkerConfig()
        )
        mock_load_config.return_value = config
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='show')
            
            assert result == 0
            mock_echo.assert_called_once()
            # Check output contains config data
            output = mock_echo.call_args[0][0]
            assert 'head' in output.lower() or 'port' in output.lower()

    @patch('scheduler.cli.config.load_config')
    def test_config_get_without_key(self, mock_load_config):
        """Test config get without key"""
        mock_load_config.return_value = Config()
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='get')
            
            assert result == 2  # Validation error
            mock_echo.assert_called_once_with("Error: key required for 'get' command")

    @patch('scheduler.cli.config.load_config')
    def test_config_get_simple_key(self, mock_load_config):
        """Test config get with simple key"""
        config = Config(address="localhost:8265")
        mock_load_config.return_value = config
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='get', key='address')
            
            assert result == 0
            mock_echo.assert_called_once()

    @patch('scheduler.cli.config.load_config')
    def test_config_get_nested_key(self, mock_load_config):
        """Test config get with nested key"""
        config = Config(
            head=HeadConfig(port=9000, heartbeat_timeout=60)
        )
        mock_load_config.return_value = config
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='get', key='head.port')
            
            assert result == 0
            mock_echo.assert_called_once()

    @patch('scheduler.cli.config.load_config')
    def test_config_set_without_key(self, mock_load_config):
        """Test config set without key"""
        mock_load_config.return_value = Config()
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='set', value='test_value')
            
            # Should fail validation
            assert result in [1, 2]

    @patch('scheduler.cli.config.load_config')
    def test_config_set_without_value(self, mock_load_config):
        """Test config set without value"""
        mock_load_config.return_value = Config()
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='set', key='test_key')
            
            # Should fail validation
            assert result in [1, 2]

    @patch('scheduler.cli.config.load_config')
    @patch('scheduler.cli.config.save_config')
    def test_config_set_valid(self, mock_save_config, mock_load_config):
        """Test config set with valid key and value"""
        config = Config(address="localhost:8265")
        mock_load_config.return_value = config
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='set', key='address', value='newhost:9000')
            
            assert result == 0
            mock_save_config.assert_called_once()

    @patch('scheduler.cli.config.load_config')
    def test_config_file_not_found(self, mock_load_config):
        """Test config command when config file doesn't exist"""
        mock_load_config.side_effect = FileNotFoundError("Config not found")
        
        with patch('scheduler.cli.config.click.echo') as mock_echo:
            result = config_command(command='show')
            
            assert result == 4
            mock_echo.assert_called()

    def test_config_unknown_command(self):
        """Test config command with unknown subcommand"""
        result = config_command(command='unknown_command')
        
        # Should return error code
        assert result != 0
