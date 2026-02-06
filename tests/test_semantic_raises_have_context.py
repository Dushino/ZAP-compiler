import os
import re
import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))

# A simple linter: find 'raise SemanticError(' occurrences and ensure the
# same line includes either 'line=' or 'col=' or 'node=' to encourage attaching
# position/context information. Some cases are legitimate (e.g., low-level helpers
# that are later wrapped with context). We will fail the test to surface spots
# for manual review and remediation.

PAT = re.compile(r"raise\s+SemanticError\s*\(")


def iter_py_files(root):
    for dirpath, dirs, files in os.walk(root):
        # Skip virtual envs and generated_tests
        if 'generated_tests' in dirpath or 'python_venv' in dirpath:
            continue
        for fn in files:
            if fn.endswith('.py'):
                yield os.path.join(dirpath, fn)


def check_line_has_context(line: str) -> bool:
    # Check for explicit line/col/node kwargs on the same line
    return ('line=' in line) or ('col=' in line) or ('node=' in line)


def test_semantic_raises_have_context():
    offenders = []
    for path in iter_py_files(ROOT):
        with open(path, 'r', encoding='utf-8') as f:
            for idx, line in enumerate(f, start=1):
                m = PAT.search(line)
                if not m:
                    continue
                # Ignore occurrences that are commented out (e.g., the test file's own explanatory comment)
                comment_pos = line.find('#')
                if comment_pos != -1 and comment_pos < m.start():
                    continue
                if not check_line_has_context(line):
                    offenders.append(f"{path}:{idx}: {line.strip()}")
    if offenders:
        pytest.fail("Found SemanticError raises without explicit context (line/col/node):\n" + "\n".join(offenders))
