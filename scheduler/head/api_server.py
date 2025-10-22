import logging
import threading
from typing import Optional

import uvicorn
from fastapi import FastAPI

from scheduler.head.job_manager import JobManager
from scheduler.head.node_manager import NodeManager
from scheduler.core.config import Config
from scheduler.core.exceptions import PermissionDeniedException
from scheduler.core import constants
from scheduler.api.routes import create_app

logger = logging.getLogger(__name__)


class APIServer:
    """HTTP API server using FastAPI"""

    def __init__(
        self,
        job_manager: JobManager,
        node_manager: NodeManager,
        config: Config
    ):
        """
        Initialize API server.

        Args:
            job_manager: JobManager instance
            node_manager: NodeManager instance
            config: Configuration instance
        """
        self.job_manager = job_manager
        self.node_manager = node_manager
        self.config = config

        # Get server configuration
        head_config = config.get('head_node', {})
        self.host = head_config.get('host', '0.0.0.0')
        self.port = head_config.get('port', constants.DEFAULT_HEAD_PORT)

        # Create FastAPI app
        self.app = create_app(job_manager, node_manager)

        # Server state
        self.server: Optional[uvicorn.Server] = None
        self.server_thread: Optional[threading.Thread] = None

        logger.info(f"API server initialized on {self.host}:{self.port}")

    def start(self):
        """
        Start the API server.

        Raises:
            PermissionDeniedException: If cannot bind to port
        """
        if self.server_thread and self.server_thread.is_alive():
            logger.warning("API server is already running")
            return

        try:
            # Create uvicorn server configuration
            config = uvicorn.Config(
                self.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            self.server = uvicorn.Server(config)

            # Start server in a separate thread
            self.server_thread = threading.Thread(target=self.server.run, daemon=True)
            self.server_thread.start()

            logger.info(f"API server started on http://{self.host}:{self.port}")
        except OSError as e:
            if "Address already in use" in str(e) or "Permission denied" in str(e):
                raise PermissionDeniedException(
                    f"Cannot bind to port {self.port}. Port may be in use or requires elevated permissions."
                )
            raise

    def stop(self):
        """
        Stop the API server.
        """
        if self.server:
            logger.info("Stopping API server...")
            self.server.should_exit = True

            # Wait for server thread to finish
            if self.server_thread and self.server_thread.is_alive():
                self.server_thread.join(timeout=5)

            self.server = None
            self.server_thread = None
            logger.info("API server stopped")
        else:
            logger.warning("API server is not running")

    def get_app(self) -> FastAPI:
        """
        Get FastAPI application instance.

        Returns:
            FastAPI app
        """
        return self.app
