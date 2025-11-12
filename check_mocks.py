#!/usr/bin/env python3
"""
Mock Specification Linter for GPU Scheduler Tests

Enforces the mock specification guidelines from tests/README.md:
1. Never use bare Mock() or MagicMock() without specs
2. Always use autospec=True for @patch() calls
3. Use spec_set=True for internal code with create_autospec
4. Use spec (not spec_set) only for external libraries when necessary

This prevents API mismatches from going undetected in tests.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict

# Patterns to detect mock usage
BARE_MOCK_PATTERN = re.compile(r'\b(Mock|MagicMock)\(\s*\)', re.IGNORECASE)
MOCK_WITH_SPEC_PATTERN = re.compile(r'\b(Mock|MagicMock)\(.*?(?:spec|autospec)=', re.IGNORECASE)
PATCH_WITHOUT_AUTOSPEC = re.compile(r'@patch\([\'"][\w.]+[\'"](?!.*autospec)', re.IGNORECASE)
PATCH_WITH_AUTOSPEC = re.compile(r'@patch\([\'"][\w.]+[\'"].*autospec=True', re.IGNORECASE)
CREATE_AUTOSPEC_WITHOUT_SPEC_SET = re.compile(r'create_autospec\([^)]+\)(?!.*spec_set=True)', re.IGNORECASE)
MOCK_OPEN_PATTERN = re.compile(r'mock_open\(')

# Allowed bare Mock() patterns (exceptions)
ALLOWED_EXCEPTIONS = [
    r'Mock\(side_effect=',  # Mock with side_effect is often okay
    r'Mock\(return_value=',  # Mock with return_value is often okay
    r'Mock\(spec=subprocess\.CompletedProcess\)',  # External library spec
    r'Mock\(spec=[A-Z]\w+\)',  # Mock with spec parameter
    r'MagicMock\(\).*# Mock.*(?:pynvml|module|C library)',  # Documented exceptions
    r'app\.\w+ = Mock\(\)',  # TUI app method mocks (simple behavior mocks)
    r'screen\.\w+ = Mock\(\)',  # TUI screen method mocks
    r'table\.\w+ = Mock\(\)',  # TUI table method mocks
    r'widget\.\w+ = Mock\(\)',  # TUI widget method mocks
]

EXCEPTION_PATTERNS = [re.compile(pattern) for pattern in ALLOWED_EXCEPTIONS]


def get_test_files() -> List[Path]:
    """Get all Python test files"""
    test_dir = Path("tests")
    return [f for f in test_dir.rglob("test_*.py") if "__pycache__" not in str(f)]


def is_exception(line: str, context_lines: List[str]) -> bool:
    """Check if this mock usage is an allowed exception"""
    # Check current line for exceptions
    for pattern in EXCEPTION_PATTERNS:
        if pattern.search(line):
            return True

    # Check if mock_open is nearby (cannot use autospec)
    for ctx_line in context_lines:
        if MOCK_OPEN_PATTERN.search(ctx_line):
            return True

    # Check if there's a comment explaining the exception
    if '# Mock' in line or '# Cannot use' in line or '# External' in line:
        return True

    return False


def check_bare_mocks(file_path: Path) -> List[Dict]:
    """Check for bare Mock() or MagicMock() without specifications"""
    violations = []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        # Skip comments
        if line.strip().startswith('#'):
            continue

        # Check for bare Mock() or MagicMock()
        bare_match = BARE_MOCK_PATTERN.search(line)
        if bare_match:
            # Check if it has spec in the same line or is an exception
            spec_match = MOCK_WITH_SPEC_PATTERN.search(line)
            context = lines[max(0, line_num-3):min(len(lines), line_num+2)]

            if not spec_match and not is_exception(line, context):
                violations.append({
                    'file': str(file_path),
                    'line': line_num,
                    'code': line.strip(),
                    'type': 'bare_mock',
                    'error': (
                        'Bare Mock() without spec. Use create_autospec(ClassName, instance=True, spec_set=True) '
                        'or Mock(spec=ClassName) instead.'
                    )
                })

    return violations


def check_patch_decorators(file_path: Path) -> List[Dict]:
    """Check for @patch() decorators without autospec=True"""
    violations = []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        # Check for @patch without autospec
        if '@patch' in line and 'autospec' not in line:
            # Check if it's @patch.object (different rules)
            if '@patch.object' in line:
                continue

            # Check for exceptions (mock_open, etc.)
            context = lines[max(0, line_num-2):min(len(lines), line_num+3)]
            if is_exception(line, context):
                continue

            # Check if new_callable is used (e.g., new_callable=mock_open)
            if 'new_callable' in line:
                continue

            violations.append({
                'file': str(file_path),
                'line': line_num,
                'code': line.strip(),
                'type': 'patch_no_autospec',
                'error': (
                    '@patch() decorator missing autospec=True. '
                    'Add autospec=True to validate function signatures.'
                )
            })

    return violations


def check_create_autospec(file_path: Path) -> List[Dict]:
    """Check for create_autospec() without spec_set=True for internal code"""
    violations = []

    with open(file_path, 'r') as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        # Check for create_autospec without spec_set
        if 'create_autospec' in line:
            # Check if spec_set=True is present
            if 'spec_set=True' not in line and 'spec_set=' not in line:
                # Get context to check if this is internal or external code
                # Look for scheduler module imports (internal code)
                context = '\n'.join(lines[max(0, line_num-10):line_num])

                # Check if we're mocking internal scheduler code
                is_internal = any([
                    'from scheduler.' in context,
                    'import scheduler.' in context,
                    'GPUMonitor' in line,
                    'SchedulerClient' in line,
                    'JobManager' in line,
                    'NodeManager' in line,
                    'Job' in line and 'scheduler' in context,
                    'Node' in line and 'scheduler' in context,
                ])

                # For internal code, spec_set should be used
                if is_internal:
                    violations.append({
                        'file': str(file_path),
                        'line': line_num,
                        'code': line.strip(),
                        'type': 'autospec_no_spec_set',
                        'error': (
                            'create_autospec() for internal code should use spec_set=True. '
                            'Add spec_set=True to catch attribute typos.'
                        )
                    })

    return violations


def main():
    """Main linter function"""
    test_files = get_test_files()
    all_violations = []

    for file_path in test_files:
        violations = []
        violations.extend(check_bare_mocks(file_path))
        violations.extend(check_patch_decorators(file_path))
        violations.extend(check_create_autospec(file_path))
        all_violations.extend(violations)

    # Group violations by type
    by_type = {}
    for v in all_violations:
        vtype = v['type']
        if vtype not in by_type:
            by_type[vtype] = []
        by_type[vtype].append(v)

    # Report violations
    if all_violations:
        print(f"Found {len(all_violations)} mock specification violations:\n")

        for vtype, violations in by_type.items():
            print(f"\n{'='*80}")
            print(f"{vtype.upper().replace('_', ' ')} ({len(violations)} violations)")
            print(f"{'='*80}\n")

            for v in violations[:10]:  # Show first 10 of each type
                print(f"{v['file']}:{v['line']}")
                print(f"  {v['code']}")
                print(f"  ERROR: {v['error']}\n")

            if len(violations) > 10:
                print(f"  ... and {len(violations) - 10} more\n")

        print(f"\nTotal violations: {len(all_violations)}")
        print("\nTo fix these issues, see tests/README.md - Mock Specification Guidelines")
        return 1
    else:
        print("✓ No mock specification violations found!")
        print("All mocks follow the guidelines in tests/README.md")
        return 0


if __name__ == "__main__":
    sys.exit(main())
