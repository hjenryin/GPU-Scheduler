"""Utility functions for parsing tqdm output from stderr."""

import re
from typing import Optional


def parse_tqdm_eta(stderr_content: str) -> Optional[str]:
    """
    Parse ETA from tqdm output in stderr.

    tqdm outputs progress bars to stderr with format like:
    - "100%|██████████| 100/100 [00:10<00:00, 10.00it/s]"
    - " 50%|█████     | 50/100 [00:05<00:05,  9.50it/s]"

    This function extracts the ETA (time remaining) from the last line of stderr.

    Args:
        stderr_content: Content of stderr log file

    Returns:
        ETA string (e.g., "00:05", "01:23:45") if found, None otherwise
    """
    if not stderr_content:
        return None

    # Get the last non-empty line
    lines = stderr_content.strip().split('\n')
    if not lines:
        return None

    last_line = lines[-1].strip()
    if not last_line:
        return None

    # tqdm format: percentage|bar| count [elapsed<remaining, speed]
    # Look for pattern: [HH:MM:SS<HH:MM:SS, ...] or [MM:SS<MM:SS, ...]
    # The ETA is after the '<' character

    # Pattern to match tqdm output with ETA
    # Examples:
    # - [00:10<00:05, 10.00it/s]
    # - [01:23:45<02:15:30, 100.00it/s]
    pattern = r'\[[\d:]+<([\d:]+),'

    match = re.search(pattern, last_line)
    if match:
        eta = match.group(1)
        # Validate that it's a time format (HH:MM:SS or MM:SS or SS)
        if re.match(r'^\d{1,2}:\d{2}(:\d{2})?$', eta) or re.match(r'^\d+$', eta):
            return eta

    return None


def format_eta_display(eta: Optional[str]) -> str:
    """
    Format ETA for display in TUI.

    Args:
        eta: ETA string from parse_tqdm_eta (e.g., "00:05", "01:23:45")

    Returns:
        Formatted ETA string for display (e.g., "ETA: 5s", "ETA: 1h 23m")
    """
    if not eta:
        return "-"

    # Parse the ETA string
    parts = eta.split(':')

    try:
        if len(parts) == 3:
            # HH:MM:SS format
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])

            if hours > 0:
                return f"ETA: {hours}h {minutes}m"
            elif minutes > 0:
                return f"ETA: {minutes}m {seconds}s"
            else:
                return f"ETA: {seconds}s"
        elif len(parts) == 2:
            # MM:SS format
            minutes = int(parts[0])
            seconds = int(parts[1])

            if minutes > 0:
                return f"ETA: {minutes}m {seconds}s"
            else:
                return f"ETA: {seconds}s"
        elif len(parts) == 1:
            # SS format
            seconds = int(parts[0])
            return f"ETA: {seconds}s"
    except ValueError:
        # If parsing fails, return the raw ETA
        return f"ETA: {eta}"

    return "-"
