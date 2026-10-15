"""Development verification of trusted fixtures, not the production sandbox.

All program execution happens in fresh, time-limited Python subprocesses.
The parent only parses, transpiles, and syntax-checks emitted code.
"""

import ast
import builtins
import json
from pathlib import Path
import subprocess
import sys

import pytest

from compiler.src import compile, transpile

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = sorted((ROOT / 'compiler/tests/conformance').glob('*.zak'))
REFERENCES = sorted((ROOT / 'zakbench/tasks').glob('*/reference.zak'))


def python_source(path):
    result = compile(path.read_text(encoding='utf-8'))
    assert result.ok and result.ast is not None, result.errors
    return transpile(result.ast)


@pytest.mark.parametrize('path', FIXTURES + REFERENCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_corpus_emits_syntactically_valid_python(path, tmp_path):
    source = python_source(path)
    ast.parse(source, feature_version=(3, 12))
    builtins.compile(source, '<transpiled>', 'exec')
    # Also exercise CPython's actual py_compile command outside the test process.
    emitted = tmp_path / 'output.py'
    emitted.write_text(source, encoding='utf-8')
    checked = subprocess.run([sys.executable, '-I', '-m', 'py_compile', str(emitted)],
                             cwd=tmp_path, capture_output=True, timeout=5)
    assert checked.returncode == 0, checked.stderr.decode()


@pytest.mark.parametrize('path', FIXTURES, ids=lambda p: p.stem)
def test_trusted_fixture_output_matches_expected(path, tmp_path):
    emitted = tmp_path / 'program.py'
    emitted.write_text(python_source(path), encoding='utf-8')
    result = subprocess.run([sys.executable, '-I', str(emitted)], cwd=tmp_path,
                            capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == path.with_suffix('.expected').read_bytes()


@pytest.mark.parametrize('path', REFERENCES, ids=lambda p: p.parent.name)
def test_trusted_reference_passes_hidden_cases(path, tmp_path):
    emitted = tmp_path / 'reference.py'
    emitted.write_text(python_source(path), encoding='utf-8')
    task = json.loads((path.parent / 'task.json').read_text())
    cases = json.loads((path.parent / 'hidden_tests.json').read_text())
    case_file = tmp_path / 'cases.json'
    case_file.write_text(json.dumps(cases), encoding='utf-8')
    # The runner and hidden-case data stay in the child. Do not log case contents.
    runner = tmp_path / 'check_reference.py'
    runner.write_text('''import json
from pathlib import Path
import runpy
import sys

namespace = runpy.run_path(sys.argv[1])
solution = namespace[sys.argv[3]]
cases = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for case in cases:
    if solution(*case["inputs"]) != case["expected"]:
        raise SystemExit("Reference result mismatch")
print(json.dumps({"passed": len(cases)}))
''', encoding='utf-8')
    result = subprocess.run([sys.executable, '-I', str(runner), str(emitted), str(case_file), task['functionName']],
                            cwd=tmp_path, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode()
    assert json.loads(result.stdout) == {'passed': len(cases)}
