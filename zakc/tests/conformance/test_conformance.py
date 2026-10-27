"""SD-35 compile/transpile/execute checks using the real Docker sandbox.

Docker and its prebuilt sandbox image are required. Missing dependencies fail
these tests; there are no skips and no local execution fallback.
"""

import ast
import builtins
import json
from pathlib import Path

import pytest

import zakc
from sandbox.runner import execute_program
from zakbench.evaluation.evaluator import evaluate


ROOT = Path(__file__).resolve().parents[3]
CORPUS = Path(__file__).resolve().parent
PROGRAM_NAMES = (
    "001_variables", "002_integer_arithmetic", "003_float_arithmetic",
    "004_boolean_logic", "005_conditionals", "006_nested_conditionals",
    "007_while_loop", "008_range_loop", "009_array_iteration", "010_functions",
    "011_recursion", "012_arrays", "013_strings", "014_maps", "015_break_continue",
)
SAMPLE_TASKS = ("array_sum", "palindrome", "frequency_count")


def python_source(path):
    """Only compile and syntax-check on the host; never execute generated code."""
    source = zakc.zak_transpile(path.read_text(encoding="utf-8")).source
    ast.parse(source, feature_version=(3, 12))
    builtins.compile(source, str(path.with_suffix(".py")), "exec", dont_inherit=True)
    return source


@pytest.mark.parametrize("name", PROGRAM_NAMES)
def test_program_stdout(name):
    path = CORPUS / f"{name}.zak"
    # Expected stdout is read by the host only and is never mounted in Docker.
    expected = path.with_suffix(".expected").read_bytes()
    result = execute_program(python_source(path))
    assert result.outcome == "pass", f"{name}: {result.outcome}: {result.detail}"
    assert result.stdout == expected


@pytest.mark.parametrize("task_id", SAMPLE_TASKS)
def test_sample_reference_hidden_tests(task_id):
    folder = ROOT / "zakbench" / "tasks" / task_id
    source = python_source(folder / "reference.zak")
    total = len(json.loads((folder / "hidden_tests.json").read_text(encoding="utf-8")))
    result = evaluate(source, task_id, "python")
    # Do not print hidden values or the evaluator's model-facing failure summary.
    assert result.exec_outcome == "pass", f"{task_id}: {result.exec_outcome}"
    assert result.compile_ok is True
    assert result.tests_total == total
    assert result.tests_passed == total
    assert result.per_test == [True] * total


def test_evaluator_ignores_direct_candidate_stdout():
    """Native/subprocess output must not corrupt the final grader report."""
    result = evaluate(
        "import os\nos.write(1, b'debug\\n')\n"
        "def solve(nums): return sum(nums)\n",
        "array_sum", "python",
    )
    assert result.exec_outcome == "pass"
    assert result.tests_passed == result.tests_total == 6
