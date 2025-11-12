#!/usr/bin/env python3
"""
Mock Specification Linter for GPU Scheduler Tests

Enforces the mock specification guidelines from tests/README.md:
1. Never use bare Mock() or MagicMock() without specs
2. Always use autospec=True for @patch() calls
3. Use spec_set=True for internal code with create_autospec
4. Use spec (not spec_set) only for external libraries when necessary

This prevents API mismatches from going undetected in tests.

Uses AST parsing for accurate detection of mock usage patterns.
"""

import ast
import sys
from pathlib import Path
from typing import List, Dict, Set, Optional


# Known external libraries that can't use autospec
EXTERNAL_LIBRARIES = {
    'pynvml',
    'subprocess',
    'httpx',
    'requests',
}

# Known internal scheduler classes
INTERNAL_CLASSES = {
    'GPUMonitor', 'SchedulerClient', 'JobManager', 'NodeManager',
    'Job', 'Node', 'Orchestrator', 'HeartbeatManager', 'FileHandler',
    'GitSnapshot', 'WorkerDaemon', 'JobExecutor',
}


class MockVisitor(ast.NodeVisitor):
    """AST visitor to detect mock usage violations"""

    def __init__(self, source_lines: List[str]):
        self.violations = []
        self.source_lines = source_lines
        self.scheduler_imports = set()  # Track scheduler imports
        self.in_function = False

    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Track imports from scheduler modules"""
        if node.module and node.module.startswith('scheduler.'):
            for alias in node.names:
                self.scheduler_imports.add(alias.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Track when we're inside a function and check decorators"""
        old_in_function = self.in_function
        self.in_function = True

        # Check @patch decorators
        for decorator in node.decorator_list:
            self._check_patch_decorator(decorator)

        self.generic_visit(node)
        self.in_function = old_in_function

    def visit_Call(self, node: ast.Call):
        """Check Mock() and create_autospec() calls"""
        func_name = self._get_func_name(node.func)

        if func_name in ('Mock', 'MagicMock'):
            self._check_bare_mock(node)
        elif func_name == 'create_autospec':
            self._check_create_autospec(node)

        self.generic_visit(node)

    def _get_func_name(self, node: ast.expr) -> Optional[str]:
        """Get the function name from a call node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return None

    def _get_line(self, lineno: int) -> str:
        """Get source line by number"""
        if 0 < lineno <= len(self.source_lines):
            return self.source_lines[lineno - 1].strip()
        return ""

    def _has_keyword(self, node: ast.Call, keyword: str) -> bool:
        """Check if a call has a specific keyword argument"""
        return any(kw.arg == keyword for kw in node.keywords)

    def _get_keyword_value(self, node: ast.Call, keyword: str) -> Optional[ast.expr]:
        """Get the value of a keyword argument"""
        for kw in node.keywords:
            if kw.arg == keyword:
                return kw.value
        return None

    def _is_behavior_mock(self, node: ast.Call) -> bool:
        """Check if this is a simple behavior mock (side_effect, return_value)"""
        return (self._has_keyword(node, 'side_effect') or
                self._has_keyword(node, 'return_value'))

    def _is_attribute_assignment(self, node: ast.Call) -> bool:
        """Check if Mock() is being assigned to an attribute (e.g., app.method = Mock())"""
        # Walk up the tree to see if this is part of an attribute assignment
        parent = getattr(node, '_parent', None)
        if isinstance(parent, ast.Assign):
            for target in parent.targets:
                if isinstance(target, ast.Attribute):
                    return True
        return False

    def _check_bare_mock(self, node: ast.Call):
        """Check for bare Mock() without specs - STRICT MODE"""
        # ONLY allow if it has spec, autospec, or spec_set
        if (self._has_keyword(node, 'spec') or
            self._has_keyword(node, 'autospec') or
            self._has_keyword(node, 'spec_set')):
            return

        # Special case: mock_open() is a factory function, not a bare Mock
        line = node.lineno
        context_lines = self.source_lines[max(0, line-4):min(len(self.source_lines), line+3)]
        if any('mock_open' in l for l in context_lines):
            return

        # Otherwise, this is a violation - bare Mock() should NEVER happen
        func_name = self._get_func_name(node.func)

        # Provide helpful error message based on context
        error_msg = (
            f'Bare {func_name}() without spec. '
            'Use create_autospec(ClassName, instance=True, spec_set=True) for internal classes, '
            'or Mock(spec=ClassName) for external libraries.'
        )

        self.violations.append({
            'file': '<will be set by caller>',
            'line': node.lineno,
            'code': self._get_line(node.lineno),
            'type': 'bare_mock',
            'error': error_msg
        })

    def _check_patch_decorator(self, decorator: ast.expr):
        """Check @patch() decorators for autospec=True"""
        # Handle @patch(...) and @patch.object(...)
        if isinstance(decorator, ast.Call):
            func = decorator.func

            # Skip @patch.object
            if isinstance(func, ast.Attribute) and func.attr == 'object':
                return

            # Check if it's @patch
            func_name = self._get_func_name(func)
            if func_name != 'patch':
                return

            # Skip if autospec is present
            if self._has_keyword(decorator, 'autospec'):
                return

            # Skip if new_callable is used (e.g., new_callable=mock_open)
            if self._has_keyword(decorator, 'new_callable'):
                return

            # Check for explanatory comment
            source_line = self._get_line(decorator.lineno)
            if any(marker in source_line for marker in ['# Mock', '# Cannot use', '# External']):
                return

            # Check if near mock_open
            line = decorator.lineno
            context_lines = self.source_lines[max(0, line-3):min(len(self.source_lines), line+3)]
            if any('mock_open' in l for l in context_lines):
                return

            self.violations.append({
                'file': '<will be set by caller>',
                'line': decorator.lineno,
                'code': self._get_line(decorator.lineno),
                'type': 'patch_no_autospec',
                'error': (
                    '@patch() decorator missing autospec=True. '
                    'Add autospec=True to validate function signatures.'
                )
            })

    def _check_create_autospec(self, node: ast.Call):
        """Check create_autospec() for spec_set=True on internal code"""
        # Skip if spec_set is already present
        if self._has_keyword(node, 'spec_set'):
            return

        # Try to determine if this is internal scheduler code
        if not node.args:
            return

        # Get the class being mocked
        first_arg = node.args[0]
        class_name = None

        if isinstance(first_arg, ast.Name):
            class_name = first_arg.id
        elif isinstance(first_arg, ast.Attribute):
            class_name = first_arg.attr

        if not class_name:
            return

        # Check if it's an internal class
        is_internal = (
            class_name in INTERNAL_CLASSES or
            class_name in self.scheduler_imports
        )

        # For external libraries, spec_set is optional
        if any(lib in self._get_line(node.lineno).lower() for lib in EXTERNAL_LIBRARIES):
            is_internal = False

        if is_internal:
            self.violations.append({
                'file': '<will be set by caller>',
                'line': node.lineno,
                'code': self._get_line(node.lineno),
                'type': 'autospec_no_spec_set',
                'error': (
                    f'create_autospec({class_name}) for internal code should use spec_set=True. '
                    'Add spec_set=True to catch attribute typos.'
                )
            })


def get_test_files() -> List[Path]:
    """Get all Python test files"""
    test_dir = Path("tests")
    return [f for f in test_dir.rglob("test_*.py") if "__pycache__" not in str(f)]


def check_file(file_path: Path) -> List[Dict]:
    """Check a single file for mock violations using AST"""
    try:
        with open(file_path, 'r') as f:
            source = f.read()
            source_lines = source.splitlines()

        # Parse the AST
        tree = ast.parse(source, filename=str(file_path))

        # Add parent references for context
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child._parent = parent

        # Visit the AST
        visitor = MockVisitor(source_lines)
        visitor.visit(tree)

        # Set the file path for all violations
        for violation in visitor.violations:
            violation['file'] = str(file_path)

        return visitor.violations

    except SyntaxError as e:
        print(f"Warning: Could not parse {file_path}: {e}", file=sys.stderr)
        return []


def main():
    """Main linter function"""
    test_files = get_test_files()
    all_violations = []

    for file_path in test_files:
        violations = check_file(file_path)
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
