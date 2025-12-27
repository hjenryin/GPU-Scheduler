"""TUI screen components."""

from scheduler.tui.screens.cluster import ClusterScreen
from scheduler.tui.screens.nodes import NodesScreen
from scheduler.tui.screens.jobs import JobsScreen
from scheduler.tui.screens.gpus import GPUsScreen
from scheduler.tui.screens.job_detail import JobDetailScreen
from scheduler.tui.screens.status import StatusScreen

__all__ = [
    "ClusterScreen",
    "NodesScreen",
    "JobsScreen",
    "GPUsScreen",
    "JobDetailScreen",
    "StatusScreen",
]
