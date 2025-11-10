#!/usr/bin/env python3
"""Detailed debug to see why files are excluded"""

import subprocess
import os
import fnmatch

workspace_root = '/home/henry/medical-sft/s2l-m1'
git_dir = os.path.join(workspace_root, '.scheduler-git')

# Get untracked files
cmd = ['git', '-c', f'safe.directory={workspace_root}', f'--git-dir={git_dir}', f'--work-tree={workspace_root}', 'ls-files', '--others']
result = subprocess.run(cmd, cwd=workspace_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
git_files = result.stdout.strip().split('\n') if result.stdout.strip() else []

print(f"Total from git ls-files --others: {len(git_files)}")

# Check our target files
target_files = [
    'm1/exp/250318-eval-medical_llm/template.makefile',
    'm1/exp/250318-eval-medical_llm/below_10b.makefile'
]

for tf in target_files:
    if tf in git_files:
        print(f"  ✓ {tf} in git_files")
    else:
        print(f"  ✗ {tf} NOT in git_files")

# Simulate the exclude pattern matching
exclude_patterns = {
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '*.so',
    '*.dylib',
    '.git',
    '.scheduler-git',
    '*.log',
    '*.swp',
    '*.swo',
    '.DS_Store',
    '.vscode',
    '.idea',
    '.mypy_cache',
    '.pytest_cache',
    '.tox',
    '.eggs',
    '.egg-info',
    'build',
    'dist',
    'wandb',
    '*.safetensors'
}

def matches_exclude(rel_path, patterns):
    """Check if path matches any exclude pattern"""
    for pat in patterns:
        if not pat:
            continue
        # Normalize pattern to use forward slashes
        p = pat.replace('\\', '/')
        if fnmatch.fnmatch(rel_path, p):
            return True, f"fnmatch({rel_path}, {p})"
        if fnmatch.fnmatch(os.path.basename(rel_path), p):
            return True, f"fnmatch(basename={os.path.basename(rel_path)}, {p})"
        # If pattern looks like a directory name or simple token,
        # check whether it's a path segment in rel_path
        if '/' not in p and p in rel_path:
            return True, f"substring: '{p}' in '{rel_path}'"
    return False, None

print("\nChecking exclude patterns:")
for tf in target_files:
    excluded, reason = matches_exclude(tf, exclude_patterns)
    if excluded:
        print(f"  ✗ {tf} EXCLUDED: {reason}")
    else:
        print(f"  ✓ {tf} NOT excluded")
