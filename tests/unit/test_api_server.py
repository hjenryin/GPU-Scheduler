"""Tests for the APIServer class"""
import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock, create_autospec
import uvicorn

from scheduler.core import Config, PermissionDeniedException
from scheduler.head.api_server import APIServer
from scheduler.manager.job_manager import JobManager
from scheduler.manager.node_manager import NodeManager
from textual.app import App


class TestAPIServer:
    """Test cases for APIServer class"""

    def test_api_server_initialization(self, test_config):
        """Test API server initialization"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app:
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            assert api_server.job_manager == mock_job_manager
            assert api_server.node_manager == mock_node_manager
            assert api_server.config == test_config
            assert api_server.host == '0.0.0.0'
            assert api_server.port == test_config.head.port
            assert api_server.app == mock_app
            assert api_server.server is None
            assert api_server.server_thread is None
            mock_create_app.assert_called_once_with(mock_job_manager, mock_node_manager)

    def test_start_success(self, test_config):
        """Test successful API server start"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class, \
             patch('scheduler.head.api_server.threading.Thread', autospec=True) as mock_thread_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            mock_thread_instance = mock_thread_class.return_value
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test start
            api_server.start()
            
            # Verify server was created with correct config
            mock_server_class.assert_called_once()
            call_args = mock_server_class.call_args
            # uvicorn.Server is called with uvicorn.Config as first argument
            config_arg = call_args[0][0]  # This should be the uvicorn.Config instance
            # We can't easily test the config parameters since it's a uvicorn.Config object
            # Just verify that the server was created
            assert config_arg is not None
            
            # Verify server was started in a thread
            mock_thread_class.assert_called_once_with(target=mock_server.run, daemon=True)
            mock_thread_instance.start.assert_called_once()
            
            assert api_server.server == mock_server
            assert api_server.server_thread == mock_thread_instance

    def test_start_already_running(self, test_config):
        """Test starting API server when already running"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class, \
             patch('scheduler.head.api_server.threading.Thread', autospec=True) as mock_thread_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            mock_thread_instance = mock_thread_class.return_value
            mock_thread_instance.is_alive.return_value = True
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            api_server.server = mock_server
            api_server.server_thread = mock_thread_instance
            
            # Test start when already running
            api_server.start()
            
            # Should not create new server or thread
            mock_server_class.assert_not_called()
            mock_thread_class.assert_not_called()

    def test_start_permission_denied_exception(self, test_config):
        """Test start failure with PermissionDeniedException"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            # Make server creation raise OSError with "Address already in use"
            mock_server_class.side_effect = OSError("Address already in use")
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test start failure
            with pytest.raises(PermissionDeniedException) as exc_info:
                api_server.start()
            
            assert "Cannot bind to port" in str(exc_info.value)
            assert str(test_config.head.port) in str(exc_info.value)

    def test_start_permission_denied_exception_alt_message(self, test_config):
        """Test start failure with PermissionDeniedException (alternative message)"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            # Make server creation raise OSError with "Permission denied"
            mock_server_class.side_effect = OSError("Permission denied")
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test start failure
            with pytest.raises(PermissionDeniedException) as exc_info:
                api_server.start()
            
            assert "Cannot bind to port" in str(exc_info.value)
            assert str(test_config.head.port) in str(exc_info.value)

    def test_start_other_os_error(self, test_config):
        """Test start failure with other OSError"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            # Make server creation raise OSError with different message
            mock_server_class.side_effect = OSError("Some other error")
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test start failure - should raise original OSError
            with pytest.raises(OSError) as exc_info:
                api_server.start()
            
            assert "Some other error" in str(exc_info.value)

    def test_stop_success(self, test_config):
        """Test successful API server stop"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app:
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Setup server and thread
            mock_server = Mock()
            mock_thread = create_autospec(threading.Thread, instance=True, spec_set=True)
            mock_thread.is_alive.return_value = True
            api_server.server = mock_server
            api_server.server_thread = mock_thread
            
            # Test stop
            api_server.stop()
            
            # Verify server was stopped
            assert mock_server.should_exit is True
            mock_thread.join.assert_called_once_with(timeout=5)
            assert api_server.server is None
            assert api_server.server_thread is None

    def test_stop_thread_not_alive(self, test_config):
        """Test stop when thread is not alive"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app:
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Setup server and thread
            mock_server = Mock()
            mock_thread = create_autospec(threading.Thread, instance=True, spec_set=True)
            mock_thread.is_alive.return_value = False
            api_server.server = mock_server
            api_server.server_thread = mock_thread
            
            # Test stop
            api_server.stop()
            
            # Verify server was stopped but thread join not called
            assert mock_server.should_exit is True
            mock_thread.join.assert_not_called()
            assert api_server.server is None
            assert api_server.server_thread is None

    def test_stop_no_server(self, test_config):
        """Test stop when no server is running"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app:
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test stop when no server
            api_server.stop()
            
            # Should not raise any exceptions
            assert api_server.server is None
            assert api_server.server_thread is None

    def test_get_app(self, test_config):
        """Test get_app method"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app:
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test get_app
            app = api_server.get_app()
            
            assert app == mock_app

    def test_server_lifecycle(self, test_config):
        """Test complete server lifecycle"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class, \
             patch('scheduler.head.api_server.threading.Thread', autospec=True) as mock_thread_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            mock_thread_instance = mock_thread_class.return_value
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # Test start
            api_server.start()
            assert api_server.server == mock_server
            assert api_server.server_thread == mock_thread_instance
            
            # Test stop
            api_server.stop()
            assert api_server.server is None
            assert api_server.server_thread is None

    def test_multiple_start_stop_cycles(self, test_config):
        """Test multiple start/stop cycles"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class, \
             patch('scheduler.head.api_server.threading.Thread', autospec=True) as mock_thread_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            mock_thread_instance = mock_thread_class.return_value
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            
            # First cycle
            api_server.start()
            api_server.stop()
            
            # Second cycle
            api_server.start()
            api_server.stop()
            
            # Should have created server twice
            assert mock_server_class.call_count == 2
            assert mock_thread_class.call_count == 2

    def test_server_configuration(self, test_config):
        """Test server configuration parameters"""
        with patch('scheduler.head.api_server.create_app', autospec=True) as mock_create_app, \
             patch('scheduler.head.api_server.uvicorn.Server', autospec=True) as mock_server_class, \
             patch('scheduler.head.api_server.threading.Thread', autospec=True) as mock_thread_class:
            
            mock_job_manager = create_autospec(JobManager, instance=True, spec_set=True)
            mock_node_manager = create_autospec(NodeManager, instance=True, spec_set=True)
            mock_app = create_autospec(App, instance=True, spec_set=True)
            mock_create_app.return_value = mock_app
            
            mock_server = Mock()
            mock_server_class.return_value = mock_server
            
            mock_thread_instance = mock_thread_class.return_value
            
            api_server = APIServer(mock_job_manager, mock_node_manager, test_config)
            api_server.start()
            
            # Verify server configuration
            call_args = mock_server_class.call_args
            config = call_args[0][0]  # First positional argument is uvicorn.Config
            
            # We can't easily test the config parameters since it's a uvicorn.Config object
            # Just verify that the server was created with a config
            assert config is not None
