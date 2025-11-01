#!/usr/bin/env python3
"""
Import Linter for GPU Scheduler

Rules:
1. Files can only import from .py files in the same directory (direct imports)
2. Files CANNOT import from their own directory's __init__.py (causes circular imports)
3. Cross-directory imports must go through __init__.py

This prevents circular imports and enforces clean module boundaries.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Set

# Pattern to match: from scheduler.X import ... (no submodule)
SCHEDULER_SAME_DIR_IMPORT_PATTERN = re.compile(r'^from scheduler\.([a-z_]+) import')
# Pattern to match: from scheduler.X.Y import ...
SCHEDULER_IMPORT_PATTERN = re.compile(r'^from scheduler\.([a-z_]+)(?:\.([a-z_]+))?(?:\..+)? import')

def get_scheduler_files() -> List[Path]:
    """Get all Python files in the scheduler package"""
    scheduler_dir = Path("scheduler")
    return [f for f in scheduler_dir.rglob("*.py") if "__pycache__" not in str(f)]

def parse_imports(file_path: Path) -> List[Tuple[int, str, str, str]]:
    """
    Parse scheduler imports from a file.

    Returns:
        List of (line_number, full_import_line, module, submodule)
    """
    imports = []
    with open(file_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            match = SCHEDULER_IMPORT_PATTERN.match(line)
            if match:
                module = match.group(1)  # e.g., "core", "head", "worker"
                submodule = match.group(2)  # e.g., "models", "config" (if present)
                imports.append((line_num, line, module, submodule))
    return imports

def check_import_violation(file_path: Path, imp_line_num: int, imp_line: str,
                          imp_module: str, imp_submodule: str) -> Tuple[bool, str]:
    """
    Check if an import violates the rules.

    Rules:
    1. Same directory imports must be direct (not through __init__.py)
    2. Cross-directory imports must use __init__.py

    Returns:
        (is_violation, error_message)
    """
    # Get the directory of the importing file
    file_parts = file_path.relative_to("scheduler").parts

    if len(file_parts) == 1:
        # Root level file (e.g., scheduler/__init__.py)
        file_dir = None
    else:
        file_dir = file_parts[0]  # e.g., "core", "head", "worker"

    # Rule 1: Files cannot import from their own directory's __init__.py
    if file_dir == imp_module and imp_submodule is None:
        # This is importing from the same directory's __init__.py
        # e.g., scheduler/core/models.py doing "from scheduler.core import X"
        return (True, f"Files must import directly from other files in the same directory, "
                     f"not from their own __init__.py. This causes circular imports. "
                     f"Use 'from scheduler.{imp_module}.<module_name> import X' instead.")

    # Rule 2: Cross-directory imports must use __init__.py
    if file_dir != imp_module and imp_submodule is not None:
        # Cross-directory import that bypasses __init__.py
        return (True, f"Cross-directory import must use __init__.py interface. "
                     f"Use 'from scheduler.{imp_module} import X' instead of "
                     f"'from scheduler.{imp_module}.{imp_submodule} import X'")

    return (False, "")

def main():
    """Main linter function"""
    scheduler_files = get_scheduler_files()
    violations = []

    for file_path in scheduler_files:
        # Skip __init__.py files - they define the public interface
        if file_path.name == "__init__.py":
            continue

        imports = parse_imports(file_path)

        for line_num, imp_line, imp_module, imp_submodule in imports:
            is_violation, error_msg = check_import_violation(
                file_path, line_num, imp_line, imp_module, imp_submodule
            )

            if is_violation:
                violations.append({
                    'file': str(file_path),
                    'line': line_num,
                    'import': imp_line,
                    'error': error_msg
                })

    # Report violations
    if violations:
        print(f"Found {len(violations)} import violations:\n")
        for v in violations:
            print(f"{v['file']}:{v['line']}")
            print(f"  {v['import']}")
            print(f"  ERROR: {v['error']}\n")
        return 1
    else:
        print("✓ No import violations found!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
