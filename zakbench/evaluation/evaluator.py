"""Score a Python or Zak candidate against a task's hidden tests in the Docker sandbox.

Generated code runs only inside the SD-21 sandbox. The only hidden-test data
that leaves this module is the bounded failure summary, which the runner
feeds back to the model as repair feedback. Nothing here logs or prints.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path

from sandbox import runner

SUMMARY_LIMIT = 500

FIXED_SUMMARIES = {
    'timeout': 'Execution timed out after {timeout_s:g}s.',
    'oom': 'Execution ran out of memory.',
    'crash': 'Execution crashed before the tests finished. Check that the code runs and defines the function.',
}


@dataclass
class EvalResult:
    exec_outcome: str  # pass, fail, timeout, oom, crash, or not_run
    tests_passed: int
    tests_total: int
    per_test: list[bool]  # empty unless the tests ran (pass or fail)
    failure_summary: str | None  # None on pass
    compile_ok: bool | None
    compile_errors: list[dict] = field(default_factory=list)
    transpiled_python: str | None = None
    execution_ms: float = 0.0


def evaluate(source, task_id, language='python', *, timeout_s=5.0, tasks_root=runner.DEFAULT_TASKS):
    """Run a candidate against the task's hidden tests and summarize the first failure.

    Raises ValueError for invalid input and RuntimeError when Docker is unavailable.
    """
    result = runner.evaluate(source, task_id, language, tasks_root=tasks_root, timeout_s=timeout_s)
    per_test = []
    if result.outcome in ('pass', 'fail'):
        failed = set(result.failed_tests)
        per_test = [index not in failed for index in range(1, result.tests_total + 1)]
    return EvalResult(
        exec_outcome=result.outcome,
        tests_passed=result.tests_passed,
        tests_total=result.tests_total,
        per_test=per_test,
        failure_summary=_failure_summary(result, Path(tasks_root) / task_id, timeout_s),
        compile_ok=result.compile_ok,
        compile_errors=result.compile_errors,
        transpiled_python=result.transpiled_python,
        execution_ms=result.execution_ms,
    )


def _failure_summary(result, task_folder, timeout_s):
    if result.outcome == 'pass':
        return None
    if result.outcome == 'fail':
        index = result.failed_tests[0]
        # The sandbox has already validated the task folder.
        cases = json.loads((task_folder / 'hidden_tests.json').read_text(encoding='utf-8'))
        case = cases[index - 1]
        got = result.first_failure_actual if result.first_failure_actual is not None else 'an exception'
        summary = (f'Test {index} of {result.tests_total} failed. Inputs: {json.dumps(case["inputs"])}. '
                   f'Expected: {json.dumps(case["expected"])}. Got: {got}.')
    elif result.outcome == 'not_run':
        summary = '\n'.join(
            f"Compile error at {error['line']}:{error['col']}: {error['code']}: {error['message']}"
            for error in result.compile_errors) or f'{result.detail or "The code was not run"}.'
    else:
        summary = FIXED_SUMMARIES[result.outcome].format(timeout_s=timeout_s)
    if len(summary) > SUMMARY_LIMIT:
        summary = summary[:SUMMARY_LIMIT - 3] + '...'
    return summary
