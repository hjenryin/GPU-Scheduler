#!/usr/bin/env python3
"""Script to collect files that would be snapshotted by the scheduler"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from typing import List, Set, Dict
import fnmatch

# Copy the relevant constants from constants.py
DEFAULT_SNAPSHOT_MAX_FILE_SIZE = 512 * 1024  # 512 KB
DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER = 1000
DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS = {
    '.json': 1 * 1024 * 1024,  # JSON files: 1 MB
    '.csv': 1 * 1024 * 1024,   # CSV files: 1 MB
}
DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS = {
    '.py', '.sh', '.yaml', '.yml', '.md',
    '.toml', '.ini', '.cfg', '.conf', '.env'
}
DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS = {
    '__pycache__', '.pytest_cache', '.mypy_cache', '.tox',
    '.egg-info', '.eggs', 'build', 'dist', '.git', '.scheduler-git',
    '*.pyc', '*.pyo', '*.pyd', '.so', '*.dylib',
     '.DS_Store', '*.swp', '*.swo',
    '.vscode', '.idea', '*.log', 'wandb', '*.safetensors'
}

def parse_scheduler_snapshot_ignore(working_dir: str) -> Set[str]:
    ignore_file = os.path.join(working_dir, '.scheduler_snapshot_ignore')
    patterns = set()
    if os.path.exists(ignore_file):
        with open(ignore_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                patterns.add(line)
    return patterns

def parse_scheduler_snapshot_include(working_dir: str) -> Set[str]:
    include_file = os.path.join(working_dir, '.scheduler_snapshot_include')
    patterns = set()
    if os.path.exists(include_file):
        with open(include_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                patterns.add(line)
    return patterns

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human readable format"""
    if size_bytes == 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} PB"

def should_include_file(file_path: str, working_dir: str) -> bool:
    try:
        rel_path = os.path.relpath(file_path, working_dir)
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            file_size = os.path.getsize(file_path)
            if ext in DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS:
                size_limit = DEFAULT_SNAPSHOT_DATA_TYPE_LIMITS[ext]
            elif ext in DEFAULT_SNAPSHOT_ALWAYS_INCLUDE_EXTENSIONS:
                return True
            else:
                size_limit = DEFAULT_SNAPSHOT_MAX_FILE_SIZE
            
            if file_size > size_limit:
                return False
        except OSError:
            return False
        return True
    except Exception:
        return False

def collect_files_to_snapshot(working_dir: str) -> List[str]:
    files_to_include = set()
    
    # First, collect from include patterns
    include_patterns = parse_scheduler_snapshot_include(working_dir)
    for pattern in include_patterns:
        import glob
        matches = glob.glob(os.path.join(working_dir, pattern), recursive=True)
        for match in matches:
            if os.path.isfile(match):
                rel_path = os.path.relpath(match, working_dir)
                files_to_include.add(rel_path)
    
    # Instead of using git ls-files, walk the directory tree and apply scheduler excludes
    # This simulates what the scheduler's shadow git would do
    user_patterns = parse_scheduler_snapshot_ignore(working_dir)
    combined_excludes = set(DEFAULT_SNAPSHOT_EXCLUDE_PATTERNS) | set(user_patterns)
    
    def matches_exclude(rel_path: str, patterns: Set[str]) -> bool:
        for pat in patterns:
            if not pat:
                continue
            p = pat.replace('\\', '/')
            if fnmatch.fnmatch(rel_path, p):
                return True
            if fnmatch.fnmatch(os.path.basename(rel_path), p):
                return True
            if '/' not in p and p in rel_path:
                return True
        return False
    
    # Walk directory tree
    git_files = []
    for root, dirs, files in os.walk(working_dir):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not matches_exclude(os.path.relpath(os.path.join(root, d), working_dir), combined_excludes)]
        
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), working_dir)
            if not matches_exclude(rel_path, combined_excludes):
                git_files.append(rel_path)
    
    filtered_git_files = []
    for rel_path in git_files:
        if rel_path in files_to_include:
            continue
        filtered_git_files.append(rel_path)
    
    # Apply size limits and folder limits
    folder_file_counts = {}
    for rel_path in git_files:
        file_path = os.path.join(working_dir, rel_path)
        folder = os.path.dirname(file_path)
        folder_file_counts[folder] = folder_file_counts.get(folder, 0) + 1
    
    for rel_path in filtered_git_files:
        if rel_path in files_to_include:
            continue
        file_path = os.path.join(working_dir, rel_path)
        folder = os.path.dirname(file_path)
        if folder_file_counts.get(folder, 0) > DEFAULT_SNAPSHOT_MAX_FILES_PER_FOLDER:
            continue
        if should_include_file(file_path, working_dir):
            files_to_include.add(rel_path)
    
    return list(files_to_include)

def main():
    if len(sys.argv) != 2:
        print("Usage: python collect_snapshot_files.py <working_dir>")
        sys.exit(1)
    
    working_dir = sys.argv[1]
    working_dir = os.path.abspath(working_dir)
    
    if not os.path.exists(working_dir):
        print(f"Directory {working_dir} does not exist")
        sys.exit(1)
    
    files = collect_files_to_snapshot(working_dir)
    
    # Calculate sizes and sort by size
    file_info = []
    for rel_path in files:
        file_path = os.path.join(working_dir, rel_path)
        try:
            size = os.path.getsize(file_path)
            file_info.append((rel_path, size))
        except OSError:
            file_info.append((rel_path, 0))
    
    # Sort by size descending
    file_info.sort(key=lambda x: x[1], reverse=True)
    
    total_size = sum(size for _, size in file_info)
    
    # Write to file
    with open('added_file_catalog.txt', 'w') as f:
        f.write(f"Total files: {len(files)}\n")
        f.write(f"Total size: {format_size(total_size)}\n\n")
        f.write("Files:\n")
        for rel_path, size in file_info:
            f.write(f"{format_size(size):>8} {rel_path}\n")
    
    print(f"Collected {len(files)} files, total size {format_size(total_size)}")
    print("Saved to added_file_catalog.txt")

if __name__ == '__main__':
    main()