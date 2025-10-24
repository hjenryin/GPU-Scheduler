import sys
import argparse

from scheduler.cli.start import start_command
from scheduler.cli.stop import stop_command
from scheduler.cli.submit import submit_command
from scheduler.cli.jobs import jobs_command
from scheduler.cli.logs import logs_command
from scheduler.cli.cancel import cancel_command
from scheduler.cli.config import config_command
from scheduler.cli.status import status_command


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog='scheduler',
        description='GPU Scheduler - Distributed job scheduling across GPU machines'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # scheduler start
    start_parser = subparsers.add_parser('start', help='Start scheduler node')
    start_parser.add_argument('--head', action='store_true', help='Start as head node')
    start_parser.add_argument('--address', help='Head node address (for workers)')
    start_parser.add_argument('--port', type=int, default=8265, help='Port number')
    start_parser.add_argument('--node-name', help='Node name')
    start_parser.add_argument('--num-gpus', type=int, help='Number of GPUs')
    start_parser.add_argument('--temp-dir', help='Temporary directory')
    start_parser.add_argument('--log-dir', help='Log directory')
    start_parser.add_argument('--block', action='store_true', default=True, help='Block until stopped')
    start_parser.add_argument('--log-level', default='INFO', help='Log level')
    
    # Head node specific options
    start_parser.add_argument('--heartbeat-timeout', type=int, help='Heartbeat timeout (head only)')
    start_parser.add_argument('--scheduling-interval', type=int, help='Scheduling interval (head only)')
    
    # Worker node specific options
    start_parser.add_argument('--gpu-poll-interval', type=int, help='GPU poll interval (worker only)')
    start_parser.add_argument('--gpu-util-threshold', type=int, help='GPU utilization threshold (worker only)')
    start_parser.add_argument('--gpu-mem-threshold', type=int, help='GPU memory threshold (worker only)')
    start_parser.add_argument('--gpu-stable-time', type=int, help='GPU stable time (worker only)')
    start_parser.add_argument('--job-startup-grace', type=int, help='Job startup grace period (worker only)')

    # scheduler stop
    stop_parser = subparsers.add_parser('stop', help='Stop scheduler')
    stop_parser.add_argument('--all', action='store_true', help='Stop all nodes in cluster (head only)')

    # scheduler submit
    submit_parser = subparsers.add_parser('submit', help='Submit a job')
    submit_parser.add_argument('script', help='Script to run')
    submit_parser.add_argument('script_args', nargs='*', help='Script arguments')
    submit_parser.add_argument('--req', default='1', help='GPU requirements')
    submit_parser.add_argument('--depends-on', dest='depends_on', nargs='*', help='Job dependencies (comma-separated)')
    submit_parser.add_argument('--name', help='Job name')
    submit_parser.add_argument('--priority', type=int, default=0, help='Priority')
    submit_parser.add_argument('--env', action='append', help='Environment variables (KEY=VALUE)')
    submit_parser.add_argument('--working-dir', help='Working directory for job')
    submit_parser.add_argument('--async', dest='async_submit', action='store_true', help='Submit async')
    submit_parser.add_argument('--log-to-driver', action='store_true', help='Stream logs')

    # scheduler jobs
    jobs_parser = subparsers.add_parser('jobs', help='List jobs')
    jobs_parser.add_argument('job_ids', nargs='*', help='Job IDs')
    jobs_parser.add_argument('--format', default='table', choices=['table', 'json', 'yaml'], help='Output format')
    jobs_parser.add_argument('--filter', default='all', help='Filter by status')
    jobs_parser.add_argument('--limit', type=int, default=50, help='Max jobs')

    # scheduler logs
    logs_parser = subparsers.add_parser('logs', help='View job logs')
    logs_parser.add_argument('job_id', help='Job ID')
    logs_parser.add_argument('-f', '--follow', action='store_true', help='Follow logs')
    logs_parser.add_argument('-n', '--lines', type=int, default=100, help='Number of lines')
    logs_parser.add_argument('--timestamps', action='store_true', help='Show timestamps')
    logs_parser.add_argument('--stderr', action='store_true', help='Show stderr')
    logs_parser.add_argument('--both', action='store_true', help='Show both stdout/stderr')

    # scheduler cancel
    cancel_parser = subparsers.add_parser('cancel', help='Cancel jobs')
    cancel_parser.add_argument('job_ids', nargs='+', help='Job IDs to cancel')

    # scheduler config
    config_parser = subparsers.add_parser('config', help='Manage configuration')
    config_parser.add_argument('subcommand', choices=['init', 'show', 'get', 'set'], help='Config command')
    config_parser.add_argument('key', nargs='?', help='Config key')
    config_parser.add_argument('value', nargs='?', help='Config value')
    config_parser.add_argument('--config-file', help='Path to configuration file')

    # scheduler status
    status_parser = subparsers.add_parser('status', help='Show cluster status (TUI)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    try:
        if args.command == 'start':
            return start_command(
                head=args.head,
                address=args.address,
                port=args.port,
                node_name=args.node_name,
                num_gpus=args.num_gpus,
                temp_dir=args.temp_dir,
                log_dir=args.log_dir,
                block=args.block,
                log_level=args.log_level,
                heartbeat_timeout=args.heartbeat_timeout,
                scheduling_interval=args.scheduling_interval,
                gpu_poll_interval=args.gpu_poll_interval,
                gpu_util_threshold=args.gpu_util_threshold,
                gpu_mem_threshold=args.gpu_mem_threshold,
                gpu_stable_time=args.gpu_stable_time,
                job_startup_grace=args.job_startup_grace
            )
        elif args.command == 'stop':
            return stop_command(all_nodes=args.all)
        elif args.command == 'submit':
            return submit_command(
                script=args.script,
                script_args=args.script_args,
                req=args.req,
                depends_on=args.depends_on,
                name=args.name,
                priority=args.priority,
                env=args.env,
                working_dir=args.working_dir,
                async_submit=args.async_submit,
                log_to_driver=args.log_to_driver
            )
        elif args.command == 'jobs':
            return jobs_command(
                job_ids=args.job_ids if args.job_ids else None,
                format=args.format,
                filter=args.filter,
                limit=args.limit
            )
        elif args.command == 'logs':
            return logs_command(
                job_id=args.job_id,
                follow=args.follow,
                lines=args.lines,
                timestamps=args.timestamps,
                stderr=args.stderr,
                both=args.both
            )
        elif args.command == 'cancel':
            return cancel_command(job_ids=args.job_ids)
        elif args.command == 'config':
            return config_command(
                command=args.subcommand,
                key=args.key,
                value=args.value,
                config_file=args.config_file
            )
        elif args.command == 'status':
            return status_command()
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())