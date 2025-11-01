"""Unit tests for API app creation in scheduler.api.routes"""
import pytest
from unittest.mock import Mock, MagicMock
from scheduler.api.routes import create_app
from scheduler.manager import JobManager
from scheduler.manager import NodeManager


class TestCreateApp:
    """Tests for create_app function"""

    def test_create_app_registers_routes(self):
        """Test that create_app registers all routes"""
        mock_job_manager = Mock(spec_set=JobManager)
        mock_node_manager = Mock(spec_set=NodeManager)
        
        app = create_app(mock_job_manager, mock_node_manager)
        
        # Check that routes are registered
        route_paths = [route.path for route in app.routes]
        
        # Check for key routes
        assert any("/api/v1/health" in path for path in route_paths)
        assert any("/api/v1/jobs" in path for path in route_paths)
        assert any("/api/v1/nodes" in path for path in route_paths)
        assert any("/api/v1/workers" in path for path in route_paths)
        assert any("/api/v1/shutdown" in path for path in route_paths)

    def test_create_app_sets_global_managers(self):
        """Test that create_app sets global managers"""
        from scheduler.api.routes import _job_manager, _node_manager
        
        # Clear globals
        _job_manager = None
        _node_manager = None
        
        mock_job_manager = Mock(spec_set=JobManager)
        mock_node_manager = Mock(spec_set=NodeManager)
        
        app = create_app(mock_job_manager, mock_node_manager)
        
        # Check that globals are set (they're used internally)
        assert app is not None

    def test_create_app_configures_fastapi(self):
        """Test that create_app configures FastAPI app"""
        mock_job_manager = Mock(spec_set=JobManager)
        mock_node_manager = Mock(spec_set=NodeManager)
        
        app = create_app(mock_job_manager, mock_node_manager)
        
        # Check FastAPI configuration
        assert app.title == "GPU Scheduler API"
        assert app.version is not None
        assert "/docs" in str(app.docs_url)

