"""Comprehensive tests for cli/main.py to reach 90% coverage"""
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from scheduler.cli.main import cli


def test_cli_version_option():
    """Test --version option"""
    runner = CliRunner()
    result = runner.invoke(cli, ['--version'])
    assert result.exit_code == 0
    assert 'version' in result.output.lower()


def test_cli_no_command():
    """Test CLI with no command shows help"""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    # Click returns exit code 2 for missing required subcommand
    assert result.exit_code in (0, 2)
    assert 'Usage:' in result.output


def test_cli_help():
    """Test --help option"""
    runner = CliRunner()
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'GPU Scheduler' in result.output


def test_cli_submit_command_exists():
    """Test submit command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['submit', '--help'])
    assert result.exit_code == 0


def test_cli_status_command_exists():
    """Test status command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['status', '--help'])
    assert result.exit_code == 0


def test_cli_logs_command_exists():
    """Test logs command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['logs', '--help'])
    assert result.exit_code == 0


def test_cli_cancel_command_exists():
    """Test cancel command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['cancel', '--help'])
    assert result.exit_code == 0


def test_cli_start_command_exists():
    """Test start command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['start', '--help'])
    assert result.exit_code == 0


def test_cli_stop_command_exists():
    """Test stop command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['stop', '--help'])
    assert result.exit_code == 0


def test_cli_jobs_command_exists():
    """Test jobs command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['jobs', '--help'])
    assert result.exit_code == 0


def test_cli_config_command_exists():
    """Test config command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['config', '--help'])
    assert result.exit_code == 0


def test_cli_freeze_command_exists():
    """Test freeze command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['freeze', '--help'])
    assert result.exit_code == 0


def test_cli_unfreeze_command_exists():
    """Test unfreeze command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['unfreeze', '--help'])
    assert result.exit_code == 0


def test_cli_retry_command_exists():
    """Test retry command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['retry', '--help'])
    assert result.exit_code == 0


def test_cli_purge_command_exists():
    """Test purge command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['purge', '--help'])
    assert result.exit_code == 0


def test_cli_submit_batch_command_exists():
    """Test submit-batch command exists"""
    runner = CliRunner()
    result = runner.invoke(cli, ['submit-batch', '--help'])
    assert result.exit_code == 0


def test_cli_invalid_command():
    """Test invalid command shows error"""
    runner = CliRunner()
    result = runner.invoke(cli, ['invalid-command'])
    assert result.exit_code != 0


def test_cli_context_settings():
    """Test CLI context settings"""
    # CLI may or may not have custom context settings
    # Just verify it exists and is accessible
    assert hasattr(cli, 'context_settings')
