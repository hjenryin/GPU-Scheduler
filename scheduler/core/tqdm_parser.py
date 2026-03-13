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

    # tqdm often rewrites a single terminal line using '\r'. Normalize both
    # CR and LF into line boundaries and scan from the most recent output.
    lines = [line.strip() for line in re.split(r'[\r\n]+', stderr_content) if line.strip()]
    if not lines:
        return None

    # tqdm format: percentage|bar| count [elapsed<remaining, speed]
    # Example matches:
    # - [00:10<00:05, 10.00it/s]
    # - [01:23:45<02:15:30, 100.00it/s]
    pattern = re.compile(r'\[[\d:]+<([\d:]+),')

    for line in reversed(lines):
        matches = list(pattern.finditer(line))
        if not matches:
            continue

        eta = matches[-1].group(1)
        # Validate HH:MM:SS, MM:SS, or SS
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
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        elif len(parts) == 2:
            # MM:SS format
            minutes = int(parts[0])
            seconds = int(parts[1])

            if minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        elif len(parts) == 1:
            # SS format
            seconds = int(parts[0])
            return f"{seconds}s"
    except ValueError:
        # If parsing fails, return the raw ETA
        return eta

    return "-"
