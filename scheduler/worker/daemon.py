import logging
import os
import socket
import signal
import threading
import time
from typing import Optional

from scheduler.core import Config, ConnectionException, get_local_ip
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.worker.job_executor import JobExecutor
from scheduler.worker.heartbeat import HeartbeatSender
from scheduler.worker.file_handler import FileHandler
from scheduler.worker.log_reader import LogChunkReader
from scheduler.worker.git_snapshot import GitSnapshotManager
from scheduler.api import SchedulerClient

logger = logging.getLogger(__name__)


class WorkerDaemon:
    """Main worker node daemon"""

    def __init__(self, config: Config, node_name: str, num_gpus: Optional[int] = None):
        """
        Initialize worker daemon.

        Args:
            config: Configuration instance
            node_name: Unique node name
            num_gpus: Number of GPUs (auto-detect if None)
        """
        self.config = config
        self.node_name = node_name
        self.running = False

        # Get head node address (from config.address or construct from head config)
        if config.address:
            self.head_address = config.address
        else:
            self.head_address = f"localhost:{config.head.port}"

        # Get worker address
        self.worker_address = f"{get_local_ip()}:{config.worker.port}"

        # Initialize GPU monitor
        self.gpu_monitor = GPUMonitor(config)

        # Detect or use specified number of GPUs
        if num_gpus is None:
            self.num_gpus = self.gpu_monitor.detect_gpus()
        else:
            self.num_gpus = num_gpus

        logger.info(f"Worker daemon initialized: node={node_name}, gpus={self.num_gpus}")

        # Initialize job executor
        self.job_executor = JobExecutor(config)

        # Initialize file handler
        self.file_handler = FileHandler(config)

        # Initialize log chunk reader for streaming logs to head
        self.log_reader = LogChunkReader(config, self.file_handler)

        # Initialize heartbeat sender
        self.heartbeat_sender = HeartbeatSender(
            node_name=node_name,
            head_address=self.head_address,
            gpu_monitor=self.gpu_monitor,
            config=config,
            log_reader=self.log_reader
        )

        # Initialize client for job operations
        self.client = SchedulerClient(address=self.head_address, config=config)

        # Track current job
        self.current_job = None
        self.current_job_pid = None

        # Setup signal handlers (only in main thread)
        if threading.current_thread() is threading.main_thread():
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)

    def start(self):
        """
        Start the worker daemon and all components.

        Raises:
            ConnectionException: If cannot connect to head node
        """
        if self.running:
            logger.warning("Worker daemon is already running")
            return

        logger.info("Starting worker daemon...")

        # Register with head node
        try:
            self.register_with_head()
        except ConnectionException as e:
            logger.error(f"Failed to register with head node: {e}")
            raise

        # Start GPU monitoring
        self.gpu_monitor.start_monitoring()

        # Set purge callback for heartbeat sender
        self.heartbeat_sender.set_purge_callback(self._handle_purge_request)

        # Start heartbeat sender
        self.heartbeat_sender.start()

        self.running = True
        logger.info("Worker daemon started successfully")

    def stop(self, graceful: bool = True):
        """
        Stop the worker daemon and all components.

        Args:
            graceful: If True, wait for jobs to complete
        """
        if not self.running:
            logger.warning("Worker daemon is not running")
            return

        logger.info("Stopping worker daemon...")

        self.running = False

        if graceful and self.current_job:
            # Wait for current job to complete
            logger.info(f"Waiting for job {self.current_job.job_id} to complete...")
            timeout = 60  # 60 seconds
            start_time = time.time()

            is_running = True
            while time.time() - start_time < timeout:
                is_running, exit_code = self.job_executor.get_job_status(self.current_job_pid)
                if not is_running:
                    break
                time.sleep(1)

            if is_running:
                logger.warning("Job did not complete in time, terminating...")
                self.job_executor.terminate_job(self.current_job_pid)

        # Stop heartbeat
        self.heartbeat_sender.stop()

        # Stop GPU monitoring
        self.gpu_monitor.stop_monitoring()

        logger.info("Worker daemon stopped")

    def run(self):
        """
        Run the worker daemon main loop (blocking).
        """
        self.start()
        self.run_main_loop()

    def run_main_loop(self):
        """
        Run the main worker loop without calling start().
        Used when start() has already been called separately.
        """
        # Main loop: poll for jobs and execute them
        logger.info("Entering main worker loop...")

        try:
            while self.running:
                # Check if shutdown was requested via heartbeat
                if self.heartbeat_sender.is_shutdown_requested():
                    logger.info("Shutdown requested by head node - stopping worker")
                    break
                
                # Poll for job assignment
                logger.info("[TRACE] Main loop: polling for job...")
                job = self.heartbeat_sender.poll_for_job()

                if job:
                    logger.info(f"[TRACE] Main loop: received job {job.job_id}")
                    self._execute_job(job)
                else:
                    logger.info("[TRACE] Main loop: no job, sleeping...")
                    # No job available, sleep briefly
                    time.sleep(5)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
            # Re-raise to propagate to parent context
            raise
        finally:
            self.stop(graceful=True)

    def register_with_head(self):
        """
        Register this worker with the head node.

        Raises:
            ConnectionException: If cannot connect to head node
        """
        try:
            logger.info(f"Registering with head node at {self.head_address}")
            response = self.client.register_node(
                node_name=self.node_name,
                address=self.worker_address,
                num_gpus=self.num_gpus
            )
            logger.info(f"Successfully registered with head node: {response}")
        except Exception as e:
            raise ConnectionException(f"Failed to register with head node: {e}")

    def _execute_job(self, job):
        """Execute a job (internal)."""
        try:
            self.current_job = job
            logger.info(f"[TRACE] Starting job {job.job_id} with env_vars: {job.env_vars}")

            # Get assigned GPUs from job
            gpu_ids = job.assigned_gpus if job.assigned_gpus else list(range(self.num_gpus))

            # Execute the job
            logger.info(f"[TRACE] Executing job {job.job_id} with GPUs: {gpu_ids}")
            pid = self.job_executor.execute_job(job, gpu_ids)
            self.current_job_pid = pid

            logger.info(f"Job {job.job_id} started with PID {pid}")

            # Monitor job execution
            while self.running:
                is_running, exit_code = self.job_executor.get_job_status(pid)

                if not is_running:
                    # Mark job as finished in log reader (will send EOF when all logs sent)
                    self.log_reader.mark_job_finished(job.job_id)

                    # Job completed - cleanup resources
                    self.job_executor.cleanup_job(job)

                    if exit_code == 0:
                        logger.info(f"Job {job.job_id} completed successfully")
                        self.client.report_job_complete(job.job_id, exit_code)
                    else:
                        logger.error(f"Job {job.job_id} failed with exit code {exit_code}")
                        self.client.report_job_failed(job.job_id, f"Exit code: {exit_code}")
                    break

                # Still running, sleep and check again
                time.sleep(5)

            self.current_job = None
            self.current_job_pid = None

        except Exception as e:
            logger.error(f"Error executing job {job.job_id}: {e}")
            # Mark job as finished in log reader
            self.log_reader.mark_job_finished(job.job_id)
            # Cleanup resources on error
            if self.current_job:
                self.job_executor.cleanup_job(self.current_job)
            try:
                self.client.report_job_failed(job.job_id, str(e))
            except Exception as report_error:
                logger.error(f"Failed to report job failure for {job.job_id}: {report_error}")
            self.current_job = None
            self.current_job_pid = None

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop(graceful=True)
        # Re-raise KeyboardInterrupt to allow proper cleanup in parent contexts
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()

    def _handle_purge_request(self, job_id: str):
        """
        Handle a purge request for a job.
        Cleans up logs and git snapshots for the job.

        Args:
            job_id: Job ID to purge
        """
        try:
            logger.info(f"Processing purge request for job {job_id}")

            # Clean up logs
            log_dir = os.path.expanduser(self.config.worker.log_dir)

            for log_type in ['stdout', 'stderr']:
                log_file = os.path.join(log_dir, f"{job_id}.{log_type}.log")
                if os.path.exists(log_file):
                    os.remove(log_file)
                    logger.info(f"Removed log file: {log_file}")

            # Clean up git snapshot
            git_manager = GitSnapshotManager(self.config)

            # Purge all snapshots for this job
            try:
                git_manager.purge_job_snapshots(job_id)
                logger.info(f"Cleaned up git snapshots for job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up git snapshots for job {job_id}: {e}")

            logger.info(f"Successfully purged job {job_id}")

        except Exception as e:
            logger.error(f"Error purging job {job_id}: {e}")
