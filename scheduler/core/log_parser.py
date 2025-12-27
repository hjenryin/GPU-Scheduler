"""Utility functions for parsing log files."""

import os
import re
import logging
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


def parse_log_file(log_path: str, limit: int = 100) -> tuple[List[Dict], Dict[str, int]]:
    """
    Parse a log file and extract WARNING and ERROR entries from the current session.
    Only includes logs after the most recent "Starting" or "started" message to filter
    out stale logs from previous daemon runs.
    
    Args:
        log_path: Path to the log file
        limit: Maximum number of unique entries to return
    
    Returns:
        Tuple of (log_entries, stats) where:
        - log_entries: List of dicts with timestamp, level, logger_name, message, count
        - stats: Dict with counts by level (WARNING, ERROR)
    """
    if not os.path.exists(log_path):
        return [], {}
    
    # Pattern to match log lines
    # Format: [2025-12-26 12:34:56] module.function:123: WARNING: message
    log_pattern = re.compile(
        r'^\[(?P<timestamp>[^\]]+)\]\s+'
        r'(?P<logger_name>\S+):'
        r'(?P<line>\d+):\s+'
        r'(?P<level>\w+):\s+'
        r'(?P<message>.+)$'
    )
    
    # Pattern to detect start messages - specifically "Starting" to mark session start
    # This should match "Starting worker daemon", "Starting orchestrator", etc.
    start_pattern = re.compile(
        r'\bStarting\b',
        re.IGNORECASE
    )
    
    try:
        # First pass: read all lines and find the most recent start marker
        all_lines = []
        last_start_index = -1
        
        with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
            for idx, line in enumerate(f):
                line = line.rstrip('\n')
                all_lines.append(line)
                
                # Check if this is a start message
                match = log_pattern.match(line)
                if match:
                    level = match.group('level')
                    message = match.group('message')
                    
                    # Look for "Starting" in INFO level logs (marks beginning of session)
                    if level == 'INFO' and start_pattern.search(message):
                        last_start_index = idx
        
        # Second pass: only process lines after the last start marker
        start_from = last_start_index if last_start_index >= 0 else 0
        
        # Store unique entries indexed by (level, logger_name, message)
        entries_dict = {}
        stats = defaultdict(int)
        
        for line in all_lines[start_from:]:
            match = log_pattern.match(line)
            
            if match:
                level = match.group('level')
                
                # Only capture WARNING and ERROR
                if level not in ['WARNING', 'ERROR']:
                    continue
                
                timestamp_str = match.group('timestamp')
                logger_name = match.group('logger_name')
                message = match.group('message')
                
                # Create key for deduplication
                key = (level, logger_name, message)
                
                if key in entries_dict:
                    # Increment count for duplicate
                    entries_dict[key]['count'] += 1
                    entries_dict[key]['timestamp'] = timestamp_str
                else:
                    # New entry
                    entries_dict[key] = {
                        'timestamp': timestamp_str,
                        'level': level,
                        'logger_name': logger_name,
                        'message': message,
                        'count': 1
                    }
                
                # Update stats
                stats[level] += 1
        
        # Convert to list and sort by timestamp (most recent first)
        entries_list = sorted(
            entries_dict.values(),
            key=lambda x: x['timestamp'],
            reverse=True
        )
        
        # Apply limit
        if limit:
            entries_list = entries_list[:limit]
        
        return entries_list, dict(stats)
    
    except Exception as e:
        logger.error(f"Error parsing log file {log_path}: {e}")
        return [], {}


def get_worker_log_path(config) -> Optional[str]:
    """
    Get the path to the worker log file.
    
    Args:
        config: Config instance
    
    Returns:
        Path to worker-{hostname}-stdout.log or None if not accessible
    """
    try:
        import socket
        log_dir = os.path.expanduser(config.worker.log_dir)
        node_name = socket.gethostname()
        worker_log = os.path.join(log_dir, f"worker-{node_name}-stdout.log")
        
        if os.path.exists(worker_log):
            return worker_log
        
        return None
    except Exception as e:
        logger.debug(f"Error getting worker log path: {e}")
        return None


def get_head_log_path(config) -> Optional[str]:
    """
    Get the path to the head log file.
    
    Args:
        config: Config instance
    
    Returns:
        Path to head-stdout.log or None if not accessible
    """
    try:
        log_dir = os.path.expanduser(config.worker.log_dir)
        head_log = os.path.join(log_dir, "head-stdout.log")
        
        if os.path.exists(head_log):
            return head_log
        
        return None
    except Exception as e:
        logger.debug(f"Error getting head log path: {e}")
        return None
