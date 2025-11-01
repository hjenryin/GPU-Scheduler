"""
Unit tests for CLI main entry point.

Tests the main() function and command routing with click.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from click.testing import CliRunner


class TestCLIMainRouting:
    """Test main CLI routing logic."""

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    def test_no_command_shows_help(self, mock_tui):
        """Test that main() shows help when no command provided."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        result = runner.invoke(cli, [])
        
        assert result.exit_code == 0  # Click returns 0 when showing help
        assert "GPU Scheduler" in result.output
        assert "Commands:" in result.output

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.start_command', autospec=True)  # Mock at the main level
    def test_routes_to_start_command(self, mock_start, mock_tui):
        """Test main() routes to start_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_start.return_value = 0
        
        result = runner.invoke(cli, ['start', '--head'])
        
        assert result.exit_code == 0
        assert mock_start.called
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs['head'] is True

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.stop_command', autospec=True)  # Mock at the main level
    def test_routes_to_stop_command(self, mock_stop, mock_tui):
        """Test main() routes to stop_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_stop.return_value = 0
        
        result = runner.invoke(cli, ['stop'])
        
        assert result.exit_code == 0
        assert mock_stop.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.submit_command', autospec=True)
    def test_routes_to_submit_command(self, mock_submit, mock_tui):
        """Test main() routes to submit_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_submit.return_value = 0
        result = runner.invoke(cli, ['submit', 'test.py'])
        
        assert result.exit_code == 0
        assert mock_submit.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.jobs_command', autospec=True)
    def test_routes_to_jobs_command(self, mock_jobs, mock_tui):
        """Test main() routes to jobs_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_jobs.return_value = 0
        result = runner.invoke(cli, ['jobs'])
        
        assert result.exit_code == 0
        assert mock_jobs.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.logs_command', autospec=True)
    def test_routes_to_logs_command(self, mock_logs, mock_tui):
        """Test main() routes to logs_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_logs.return_value = 0
        result = runner.invoke(cli, ['logs', 'job_123'])
        
        assert result.exit_code == 0
        assert mock_logs.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.cancel_command', autospec=True)
    def test_routes_to_cancel_command(self, mock_cancel, mock_tui):
        """Test main() routes to cancel_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_cancel.return_value = 0
        result = runner.invoke(cli, ['cancel', 'job_1'])
        
        assert result.exit_code == 0
        assert mock_cancel.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.config_command', autospec=True)
    def test_routes_to_config_command(self, mock_config, mock_tui):
        """Test main() routes to config_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_config.return_value = 0
        result = runner.invoke(cli, ['config', 'show'])
        
        assert result.exit_code == 0
        assert mock_config.called

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.status_command', autospec=True)
    def test_routes_to_status_command(self, mock_status, mock_tui):
        """Test main() routes to status_command."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_status.return_value = 0
        result = runner.invoke(cli, ['status'])
        
        assert result.exit_code == 0
        assert mock_status.called


class TestCLIMainExceptionHandling:
    """Test exception handling in main()."""

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.start_command', autospec=True)
    def test_handles_keyboard_interrupt(self, mock_start, mock_tui):
        """Test main() handles KeyboardInterrupt."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_start.side_effect = KeyboardInterrupt()
        result = runner.invoke(cli, ['start', '--head'])
        
        assert result.exit_code == 130

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.submit_command', autospec=True)
    def test_handles_generic_exception(self, mock_submit, mock_tui):
        """Test main() handles generic exceptions."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_submit.side_effect = RuntimeError("Test error")
        result = runner.invoke(cli, ['submit', 'test.py'])
        
        assert result.exit_code == 1


class TestCLIMainArgumentParsing:
    """Test argument parsing in main()."""

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.start_command', autospec=True)
    def test_start_command_arguments(self, mock_start, mock_tui):
        """Test start command argument parsing."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_start.return_value = 0
        result = runner.invoke(cli, [
            'start', 
            '--head', 
            '--port', '9000',
            '--node-name', 'test-node',
            '--num-gpus', '2',
            '--log-level', 'DEBUG'
        ])
        
        assert result.exit_code == 0
        assert mock_start.called
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs['head'] is True
        assert call_kwargs['port'] == 9000
        assert call_kwargs['node_name'] == 'test-node'
        assert call_kwargs['num_gpus'] == 2
        assert call_kwargs['log_level'] == 'DEBUG'

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.submit_command', autospec=True)
    def test_submit_command_arguments(self, mock_submit, mock_tui):
        """Test submit command argument parsing."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_submit.return_value = 0
        # Scheduler options must come before the command
        result = runner.invoke(cli, [
            'submit',
            '--req', '2',
            '--name', 'test-job',
            '--priority', '5',
            '--env', 'KEY1=value1',
            '--env', 'KEY2=value2',
            '--working-dir', '/tmp',
            '--block',
            'python', 'test.py',
            'arg1', 'arg2'
        ])
        
        assert result.exit_code == 0
        assert mock_submit.called
        call_kwargs = mock_submit.call_args[1]
        assert call_kwargs['command'] == ['python', 'test.py', 'arg1', 'arg2']
        assert call_kwargs['req'] == '2'
        assert call_kwargs['name'] == 'test-job'
        assert call_kwargs['priority'] == 5
        assert call_kwargs['env'] == ['KEY1=value1', 'KEY2=value2']
        assert call_kwargs['working_dir'] == '/tmp'
        assert call_kwargs['block'] is True

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.jobs_command', autospec=True)
    def test_jobs_command_arguments(self, mock_jobs, mock_tui):
        """Test jobs command argument parsing."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_jobs.return_value = 0
        result = runner.invoke(cli, [
            'jobs',
            'job1', 'job2',
            '--format', 'json',
            '--filter', 'running',
            '--limit', '10'
        ])
        
        assert result.exit_code == 0
        assert mock_jobs.called
        call_kwargs = mock_jobs.call_args[1]
        assert call_kwargs['job_ids'] == ['job1', 'job2']
        assert call_kwargs['format'] == 'json'
        assert call_kwargs['filter'] == 'running'
        assert call_kwargs['limit'] == 10

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.logs_command', autospec=True)
    def test_logs_command_arguments(self, mock_logs, mock_tui):
        """Test logs command argument parsing."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_logs.return_value = 0
        result = runner.invoke(cli, [
            'logs',
            'job123',
            '--follow',
            '--lines', '50',
            '--timestamps',
            '--stderr'
        ])
        
        assert result.exit_code == 0
        assert mock_logs.called
        call_kwargs = mock_logs.call_args[1]
        assert call_kwargs['job_id'] == 'job123'
        assert call_kwargs['follow'] is True
        assert call_kwargs['lines'] == 50
        assert call_kwargs['timestamps'] is True
        assert call_kwargs['stderr'] is True

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.config_command', autospec=True)
    def test_config_command_arguments(self, mock_config, mock_tui):
        """Test config command argument parsing."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_config.return_value = 0
        result = runner.invoke(cli, [
            'config',
            'set',
            'head.port',
            '9000',
            '--config-file', '/tmp/config.yaml'
        ])
        
        assert result.exit_code == 0
        assert mock_config.called
        call_kwargs = mock_config.call_args[1]
        assert call_kwargs['command'] == 'set'
        assert call_kwargs['key'] == 'head.port'
        assert call_kwargs['value'] == '9000'
        assert call_kwargs['config_file'] == '/tmp/config.yaml'

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    def test_version_option(self, mock_tui):
        """Test --version option."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.start_command', autospec=True)
    def test_start_block_defaults_to_false(self, mock_start, mock_tui):
        """Test that --block defaults to False when not specified."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_start.return_value = 0
        result = runner.invoke(cli, ['start', '--head'])
        
        assert result.exit_code == 0
        assert mock_start.called
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs['block'] is False

    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.start_command', autospec=True)
    def test_start_block_flag_sets_true(self, mock_start, mock_tui):
        """Test that --block flag sets block to True."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_start.return_value = 0
        result = runner.invoke(cli, ['start', '--head', '--block'])
        
        assert result.exit_code == 0
        assert mock_start.called
        call_kwargs = mock_start.call_args[1]
        assert call_kwargs['block'] is True
    @patch('scheduler.tui.run_tui', autospec=True)  # Mock the problematic textual import
    @patch('scheduler.cli.main.submit_command', autospec=True)
    def test_submit_with_conflicting_arguments(self, mock_submit, mock_tui):
        """Test submit command preserves arguments that conflict with submit options."""
        from scheduler.cli.main import cli
        runner = CliRunner()
        
        mock_submit.return_value = 0
        # Test with --req=1 before the command to set scheduler option
        # Then cmd with various args including --req=1, --name, --env that should be preserved as command args
        result = runner.invoke(cli, [
            'submit',
            '--req', '1',
            'cmd',
            '--aaa=1',
            '-d',
            '--async2',
            '-f',
            '--ff',
            'file.txt',
            '--req=1',
            '-D',
            '--name',
            '2',
            '-g',
            '--env',
            '--name',
            '3'
        ])
        
        assert result.exit_code == 0
        assert mock_submit.called
        call_kwargs = mock_submit.call_args[1]
        # Verify scheduler options
        assert call_kwargs['req'] == '1'
        # Verify command and all its arguments are preserved in order
        expected_cmd = ['cmd', '--aaa=1', '-d', '--async2', '-f', '--ff', 'file.txt', 
                       '--req=1', '-D', '--name', '2', '-g', '--env', '--name', '3']
        assert call_kwargs['command'] == expected_cmd
