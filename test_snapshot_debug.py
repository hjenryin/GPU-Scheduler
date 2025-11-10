#!/usr/bin/env python3
"""Debug script to test snapshot collection"""

from scheduler.core.config import Config
from scheduler.worker.git_snapshot import GitSnapshotManager
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

config = Config()
manager = GitSnapshotManager(config)

working_dir = '/home/henry/medical-sft/s2l-m1'

print("=" * 80)
print("Testing _collect_files_to_snapshot")
print("=" * 80)

# Call the collection method
files = manager._collect_files_to_snapshot(working_dir)

print(f"\nTotal files collected: {len(files)}")

# Check if our target files are in the list
target_files = [
    'm1/exp/250318-eval-medical_llm/template.makefile',
    'm1/exp/250318-eval-medical_llm/below_10b.makefile',
    'm1/exp/250318-eval-medical_llm/above_10b.makefile'
]

print("\nChecking target files:")
for tf in target_files:
    if tf in files:
        print(f"  ✓ {tf} - FOUND")
    else:
        print(f"  ✗ {tf} - MISSING")

# Check files in the m1/exp directory
exp_files = [f for f in files if f.startswith('m1/exp/')]
print(f"\nFiles in m1/exp/: {len(exp_files)}")
for f in sorted(exp_files):
    print(f"  {f}")
