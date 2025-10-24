"""
Unit tests for CLI main entry point.

Tests the main() function and command routing.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock


class TestCLIMainRouting:
    """Test main CLI routing logic."""

    @patch('sys.argv', ['scheduler'])
    def test_no_command_returns_error(self):
        """Test that main() returns 1 when no command provided."""
        from scheduler.cli.main import main
        exit_code = main()
        assert exit_code == 1

    def test_routes_to_start_command(self):
        """Test main() routes to start_command."""
        import scheduler.cli  # Ensures module is loaded
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'start', '--head']):
            with patch.object(main_module, 'start_command', return_value=0) as mock_start:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_start.called
                call_kwargs = mock_start.call_args[1]
                assert call_kwargs['head'] is True

    def test_routes_to_stop_command(self):
        """Test main() routes to stop_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'stop']):
            with patch.object(main_module, 'stop_command', return_value=0) as mock_stop:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_stop.called

    def test_routes_to_submit_command(self):
        """Test main() routes to submit_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'submit', 'test.py']):
            with patch.object(main_module, 'submit_command', return_value=0) as mock_submit:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_submit.called

    def test_routes_to_jobs_command(self):
        """Test main() routes to jobs_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'jobs']):
            with patch.object(main_module, 'jobs_command', return_value=0) as mock_jobs:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_jobs.called

    def test_routes_to_logs_command(self):
        """Test main() routes to logs_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'logs', 'job_123']):
            with patch.object(main_module, 'logs_command', return_value=0) as mock_logs:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_logs.called

    def test_routes_to_cancel_command(self):
        """Test main() routes to cancel_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'cancel', 'job_1']):
            with patch.object(main_module, 'cancel_command', return_value=0) as mock_cancel:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_cancel.called

    def test_routes_to_config_command(self):
        """Test main() routes to config_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'config', 'show']):
            with patch.object(main_module, 'config_command', return_value=0) as mock_config:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_config.called

    def test_routes_to_status_command(self):
        """Test main() routes to status_command."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'status']):
            with patch.object(main_module, 'status_command', return_value=0) as mock_status:
                exit_code = main_module.main()

                assert exit_code == 0
                assert mock_status.called


class TestCLIMainExceptionHandling:
    """Test exception handling in main()."""

    def test_handles_keyboard_interrupt(self):
        """Test main() handles KeyboardInterrupt."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'start', '--head']):
            with patch.object(main_module, 'start_command', side_effect=KeyboardInterrupt()):
                exit_code = main_module.main()

                assert exit_code == 130

    def test_handles_generic_exception(self):
        """Test main() handles generic exceptions."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'submit', 'test.py']):
            with patch.object(main_module, 'submit_command', side_effect=RuntimeError("Test error")):
                exit_code = main_module.main()

                assert exit_code == 1


class TestCLIMainArgumentParsing:
    """Test argument parsing in main()."""

    def test_parses_port_argument(self):
        """Test main() parses port argument correctly."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'start', '--head', '--port', '9000']):
            with patch.object(main_module, 'start_command', return_value=0) as mock_start:
                exit_code = main_module.main()

                assert exit_code == 0
                call_kwargs = mock_start.call_args[1]
                assert call_kwargs['port'] == 9000

    def test_parses_submit_arguments(self):
        """Test main() parses submit arguments correctly."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'submit', 'script.py', '--req', '2', '--priority', '5']):
            with patch.object(main_module, 'submit_command', return_value=0) as mock_submit:
                exit_code = main_module.main()

                assert exit_code == 0
                call_kwargs = mock_submit.call_args[1]
                assert call_kwargs['script'] == 'script.py'
                assert call_kwargs['req'] == '2'
                assert call_kwargs['priority'] == 5

    def test_parses_jobs_arguments(self):
        """Test main() parses jobs arguments correctly."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'jobs', '--format', 'json', '--limit', '20']):
            with patch.object(main_module, 'jobs_command', return_value=0) as mock_jobs:
                exit_code = main_module.main()

                assert exit_code == 0
                call_kwargs = mock_jobs.call_args[1]
                assert call_kwargs['format'] == 'json'
                assert call_kwargs['limit'] == 20

    def test_parses_script_args(self):
        """Test main() parses script arguments correctly."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'submit', 'script.py', 'arg1', 'arg2', '--req', '1']):
            with patch.object(main_module, 'submit_command', return_value=0) as mock_submit:
                exit_code = main_module.main()

                assert exit_code == 0
                call_kwargs = mock_submit.call_args[1]
                assert call_kwargs['script'] == 'script.py'
                assert call_kwargs['script_args'] == ['arg1', 'arg2']

    def test_parses_multiple_job_ids(self):
        """Test main() parses multiple job IDs correctly."""
        import scheduler.cli
        main_module = sys.modules['scheduler.cli.main']

        with patch('sys.argv', ['scheduler', 'jobs', 'job_1', 'job_2']):
            with patch.object(main_module, 'jobs_command', return_value=0) as mock_jobs:
                exit_code = main_module.main()

                assert exit_code == 0
                call_kwargs = mock_jobs.call_args[1]
                assert call_kwargs['job_ids'] == ['job_1', 'job_2']
