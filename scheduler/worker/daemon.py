import logging
import os
import socket
import signal
import subprocess
import threading
import time
from datetime import datetime
from typing import Optional, List

from scheduler.core import Config, ConnectionException, get_local_ip
from scheduler.worker.gpu_monitor import GPUMonitor
from scheduler.worker.job_executor import JobExecutor
from scheduler.worker.heartbeat import HeartbeatSender
from scheduler.worker.file_handler import FileHandler
from scheduler.worker.git_snapshot import GitSnapshotManager
from scheduler.worker.job_metadata_cache import JobMetadataCache
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

        # Initialize job metadata cache
        cache_dir = os.path.expanduser(config.worker.temp_dir)
        self.job_metadata_cache = JobMetadataCache(cache_dir)

        # Cleanup old system logs on startup (older than 24 hours)
        # Note: Job logs are NOT cleaned automatically - only via explicit purge commands
        logger.info("Cleaning up old system log files on startup...")
        removed_count = self.file_handler.cleanup_old_logs(max_age_hours=24, include_job_logs=False)
        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old system log files on startup")

        # Initialize heartbeat sender
        self.heartbeat_sender = HeartbeatSender(
            node_name=node_name,
            head_address=self.head_address,
            gpu_monitor=self.gpu_monitor,
            config=config
        )

        # Initialize client for job operations
        self.client = SchedulerClient(address=self.head_address, config=config)

        # Log syncing via rsync
        self.log_sync_thread: Optional[threading.Thread] = None
        self.log_dir = os.path.expanduser(config.worker.log_dir)
        self.rsync_port: Optional[int] = None  # Learned from head node during registration

        # Track active jobs (job_id -> {job, pid, start_time, monitor_thread})
        self.active_jobs = {}
        self.active_jobs_lock = threading.Lock()

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

        # Set running flag before starting threads to avoid race condition
        self.running = True

        # Start heartbeat sender
        self.heartbeat_sender.start()

        # Start log syncing via rsync (only if port is available)
        if self.rsync_port is not None:
            self._start_log_sync(self.rsync_port)
        else:
            logger.info("Skipping log sync - rsync port not available from head node")

        logger.info("Worker daemon started successfully")

    def stop(self, graceful: bool = True):
        """
        Stop the worker daemon and all components.
        Jobs are left running when worker stops.

        Args:
            graceful: Ignored - worker always exits immediately, leaving jobs running
        """
        if not self.running:
            logger.warning("Worker daemon is not running")
            return

        logger.info("Stopping worker daemon...")

        self.running = False

        # Don't wait for jobs or terminate them - let them continue running
        with self.active_jobs_lock:
            if self.active_jobs:
                logger.info(f"Leaving {len(self.active_jobs)} job(s) running (untracked): {list(self.active_jobs.keys())}")

        # Stop heartbeat
        self.heartbeat_sender.stop()

        # Log sync thread will stop when self.running = False (it's already False at this point)

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

        # Track rsync port checks (check periodically, not every iteration)
        rsync_port_check_counter = 0
        rsync_port_check_interval = 10  # Check every 10 iterations (~300 seconds with 30s poll timeout)

        try:
            while self.running:
                # Check if shutdown was requested via heartbeat
                if self.heartbeat_sender.is_shutdown_requested():
                    logger.info("Shutdown requested by head node - stopping worker")
                    break

                # Periodically check if rsync port has changed
                rsync_port_check_counter += 1
                if rsync_port_check_counter >= rsync_port_check_interval:
                    rsync_port_check_counter = 0
                    self._check_and_update_rsync_port()

                # Poll for job assignments (returns list of all jobs for this node)
                try:
                    jobs = self.client.poll_for_job(
                        self.node_name,
                        timeout=self.config.worker.job_poll_timeout
                    )
                    if jobs:
                        logger.info(f"Received {len(jobs)} job assignment(s): {[job.job_id for job in jobs]}")
                except Exception as e:
                    logger.error(f"Failed to poll for job: {e}")
                    jobs = []

                # Get set of job IDs from poll response (empty set if jobs=[])
                poll_job_ids = {job.job_id for job in jobs}

                # Detect jobs NOT in poll response
                with self.active_jobs_lock:
                    current_job_ids = set(self.active_jobs.keys())
                    jobs_to_remove = current_job_ids - poll_job_ids

                # Terminate and cleanup jobs not in poll response
                if jobs_to_remove:
                    logger.info(f"Terminating {len(jobs_to_remove)} job(s) not in poll response: {jobs_to_remove}")

                    for job_id in jobs_to_remove:
                        with self.active_jobs_lock:
                            job_info = self.active_jobs.get(job_id)

                        if job_info:
                            pid = job_info['pid']
                            job = job_info['job']

                            # Attempt to terminate the process
                            # This is idempotent - if job already completed/failed, terminate is a no-op
                            try:
                                logger.info(f"Terminating job {job_id} (PID {pid}) - not in poll response")
                                self.job_executor.terminate_job(pid)
                            except Exception as e:
                                logger.warning(f"Failed to terminate job {job_id} (PID {pid}): {e}")

                            # Clean up job resources
                            try:
                                self.job_executor.cleanup_job(job)
                            except Exception as e:
                                logger.warning(f"Failed to cleanup job {job_id}: {e}")

                        # Remove from active_jobs
                        with self.active_jobs_lock:
                            self.active_jobs.pop(job_id, None)

                    # Execute all jobs from poll response (deduplication check inside _execute_job)
                    for job in jobs:
                        self._execute_job(job)
                else:
                    # Empty poll response means no jobs assigned to this node
                    # Terminate and clean up all active jobs
                    with self.active_jobs_lock:
                        if self.active_jobs:
                            logger.info(f"No jobs in poll response, terminating and clearing {len(self.active_jobs)} job(s)")
                            jobs_to_terminate = list(self.active_jobs.items())
                    
                    # Terminate jobs outside the lock
                    for job_id, job_info in jobs_to_terminate:
                        if job_info:
                            pid = job_info['pid']
                            job = job_info['job']
                            
                            # Terminate the process
                            try:
                                logger.info(f"Terminating job {job_id} (PID {pid}) - not in poll response")
                                self.job_executor.terminate_job(pid)
                            except Exception as e:
                                logger.warning(f"Failed to terminate job {job_id} (PID {pid}): {e}")
                            
                            # Clean up job resources
                            try:
                                self.job_executor.cleanup_job(job)
                            except Exception as e:
                                logger.warning(f"Failed to cleanup job {job_id}: {e}")
                    
                    # Clear active_jobs
                    with self.active_jobs_lock:
                        self.active_jobs.clear()

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

            # Extract rsync port from registration response
            self.rsync_port = response.get('rsync_port')
            if self.rsync_port:
                logger.info(f"Head node rsync daemon available on port {self.rsync_port}")
            else:
                logger.warning("Head node rsync daemon not available - log syncing disabled")
        except Exception as e:
            raise ConnectionException(f"Failed to register with head node: {e}")

    def _execute_job(self, job):
        """Execute a job in background (non-blocking)."""
        # Check if job is already being executed (deduplication)
        with self.active_jobs_lock:
            if job.job_id in self.active_jobs:
                logger.debug(f"Job {job.job_id} already executing, ignoring duplicate")
                return

            # Reserve the job_id immediately to prevent race conditions
            self.active_jobs[job.job_id] = None  # Placeholder

        try:
            # Get assigned GPUs from job
            gpu_ids = job.assigned_gpus if job.assigned_gpus else list(range(self.num_gpus))

            # Execute the job
            pid = self.job_executor.execute_job(job, gpu_ids)

            logger.info(f"Job {job.job_id} started with PID {pid}")

            # Start monitoring thread (non-blocking)
            monitor_thread = threading.Thread(
                target=self._monitor_job,
                args=(job, pid),
                daemon=True,
                name=f"monitor-{job.job_id}"
            )
            monitor_thread.start()

            # Update active jobs with full information
            with self.active_jobs_lock:
                self.active_jobs[job.job_id] = {
                    'job': job,
                    'pid': pid,
                    'start_time': datetime.now(),
                    'monitor_thread': monitor_thread
                }

            # Store job metadata for later cleanup
            if job.snapshot_working_dir:
                self.job_metadata_cache.store_job_metadata(job.job_id, job.snapshot_working_dir)

        except Exception as e:
            # Clean up placeholder on error
            with self.active_jobs_lock:
                self.active_jobs.pop(job.job_id, None)

            logger.error(f"Error executing job {job.job_id}: {e}")
            try:
                self.client.report_job_failed(job.job_id, str(e))
            except Exception as report_error:
                logger.error(f"Failed to report job failure for {job.job_id}: {report_error}")

    def _monitor_job(self, job, pid: int):
        """Monitor job execution in background thread."""
        try:
            # Monitor job execution
            while self.running:
                is_running, exit_code = self.job_executor.get_job_status(pid)

                if not is_running:
                    # Job completed - cleanup resources and get after commit
                    after_commit_ref = self.job_executor.cleanup_job(job)

                    if exit_code == 0:
                        logger.info(f"Job {job.job_id} completed successfully")
                        self.client.report_job_complete(job.job_id, exit_code, after_commit_ref)
                    else:
                        logger.error(f"Job {job.job_id} failed with exit code {exit_code}")
                        self.client.report_job_failed(job.job_id, f"Job exited with code {exit_code}", exit_code, after_commit_ref)

                    # NOTE: Do NOT remove from active_jobs here!
                    # Jobs are removed from active_jobs only when they're no longer in the poll response.
                    # This prevents race conditions with delayed poll responses.
                    break

                # Still running, sleep and check again
                time.sleep(5)

        except Exception as e:
            logger.error(f"Error monitoring job {job.job_id}: {e}")
            # Cleanup resources on error
            self.job_executor.cleanup_job(job)
            try:
                self.client.report_job_failed(job.job_id, str(e))
            except Exception as report_error:
                logger.error(f"Failed to report job failure for {job.job_id}: {report_error}")

            # NOTE: Do NOT remove from active_jobs here either!
            # Let the poll response cleanup handle it

    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop(graceful=True)
        # Re-raise KeyboardInterrupt to allow proper cleanup in parent contexts
        if signum == signal.SIGINT:
            raise KeyboardInterrupt()


    def _purge_job_files(self, job_id: str):
        """
        Purge files for a specific job.

        Args:
            job_id: Job ID to purge
        """
        try:
            # Clean up logs
            log_dir = os.path.expanduser(self.config.worker.log_dir)

            for log_type in ['stdout', 'stderr']:
                log_file = os.path.join(log_dir, f"{job_id}.{log_type}.log")
                if os.path.exists(log_file):
                    os.remove(log_file)
                    logger.info(f"Removed log file: {log_file}")

            # Clean up git snapshot
            git_manager = GitSnapshotManager(self.config)

            # Get snapshot working directory from cache
            snapshot_working_dir = self.job_metadata_cache.get_snapshot_working_dir(job_id)

            try:
                git_manager.purge_job_snapshots(job_id, snapshot_working_dir)
                logger.info(f"Cleaned up git snapshots for job {job_id}")
            except Exception as e:
                logger.warning(f"Failed to clean up git snapshots for job {job_id}: {e}")

            # Remove job metadata from cache after successful purge
            self.job_metadata_cache.remove_job_metadata(job_id)

            logger.info(f"Successfully purged job {job_id}")

        except Exception as e:
            logger.error(f"Error purging job {job_id}: {e}")

    def _start_log_sync(self, port: int):
        """Start periodic log syncing to head node via rsync daemon.

        Args:
            port: The rsync daemon port on the head node
        """
        def sync_loop():
            """Background thread that periodically syncs job logs to head node."""
            # Extract head hostname from address
            head_host = self.head_address.split(':')[0]

            while self.running:
                try:
                    # Only sync job logs (*.log files), not worker daemon logs
                    # This ensures worker.log and other non-job logs stay local
                    # Exclude patterns for system logs (worker-*, head-*, etc.)
                    result = subprocess.run(
                        [
                            'rsync',
                            '-avz',                      # Archive, verbose, compress
                            '--append',                  # Append to growing files (perfect for logs)
                            '--timeout=30',              # Network timeout
                            '--include=*.log',           # Include .log files
                            '--exclude=worker*.log',     # Exclude worker system logs (worker.log, worker-*-stdout.log, etc.)
                            '--exclude=head*.log',       # Exclude head system logs (head-stdout.log, head-stderr.log)
                            '--exclude=*.offset',        # Exclude pygtail offset files (if any)
                            '--exclude=*',               # Exclude everything else
                            f'{self.log_dir}/',          # Source (trailing slash = contents)
                            f'rsync://{head_host}:{port}/scheduler-logs/'  # Destination
                        ],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if result.returncode == 0:
                        # Only log if files were actually transferred
                        output_lines = result.stdout.strip().split('\n')
                        if len(output_lines) > 4:  # More than just the summary lines
                            logger.debug(f"Synced job logs to head node")
                    else:
                        # Only log errors, not normal "no changes" scenarios
                        if result.returncode != 0 and result.stderr:
                            logger.warning(f"Log sync failed: {result.stderr.strip()}")

                except subprocess.TimeoutExpired:
                    logger.warning("Log sync timed out")
                except FileNotFoundError:
                    logger.error("rsync command not found - log syncing disabled")
                    break  # Don't keep trying if rsync isn't installed
                except Exception as e:
                    logger.error(f"Log sync error: {e}")

                # Sleep for 10 seconds between syncs
                time.sleep(10)

        # Start sync thread
        self.log_sync_thread = threading.Thread(target=sync_loop, daemon=True, name="LogSync")
        self.log_sync_thread.start()
        logger.info(f"Log syncing started (rsync to head:{port})")

    def _check_and_update_rsync_port(self):
        """
        Check if rsync port has changed on head node and restart log sync if needed.
        Called periodically from main worker loop.
        """
        try:
            # Get current rsync port from head node
            current_port = self.heartbeat_sender.get_rsync_port_from_heartbeat()
            
            # Check if port has changed
            if current_port is not None and current_port != self.rsync_port:
                logger.info(f"Rsync port changed from {self.rsync_port} to {current_port}, restarting log sync")
                
                # Update stored port
                old_port = self.rsync_port
                self.rsync_port = current_port
                
                # Stop old log sync thread (it will detect self.running change and exit naturally)
                # The daemon thread will exit when we restart with new port
                
                # Start new log sync with updated port
                if self.rsync_port is not None:
                    self._start_log_sync(self.rsync_port)
                    logger.info(f"Log sync restarted on new port {self.rsync_port}")
                else:
                    logger.warning("Rsync port became unavailable")
                    
            elif current_port is None and self.rsync_port is not None:
                logger.warning(f"Rsync port is no longer available (was {self.rsync_port})")
                self.rsync_port = None
                
        except Exception as e:
            logger.debug(f"Error checking rsync port: {e}")

