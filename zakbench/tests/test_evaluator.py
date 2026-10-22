"""Tests for the hidden-test evaluator. Docker is faked; run from the repository root:
python3 -m unittest discover -s zakbench/tests -t .
"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sandbox import runner
from zakbench.evaluation.evaluator import SUMMARY_LIMIT, EvalResult, evaluate

CASES = [{'inputs': [[n, n]], 'expected': n * 2} for n in (1001, 2002, 3003, 4004, 5005)]


class EvaluateTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        folder = self.root / 'pair_sum'
        folder.mkdir()
        (folder / 'task.json').write_text(json.dumps({'id': 'pair_sum', 'functionName': 'solve'}))
        (folder / 'hidden_tests.json').write_text(json.dumps(CASES))

    def run_sandbox(self, sandbox_result, source='def solve(a):\n    return sum(a)\n', language='python'):
        """Evaluate with the Docker step replaced by a fixed sandbox result."""
        with patch.object(runner, '_execute', return_value=sandbox_result) as execute:
            result = evaluate(source, 'pair_sum', language, tasks_root=self.root)
        return result, execute

    def test_pass_has_no_summary(self):
        result, _ = self.run_sandbox(runner.SandboxResult('pass', 5, 5, 40.0))
        self.assertIsInstance(result, EvalResult)
        self.assertEqual(result.exec_outcome, 'pass')
        self.assertEqual((result.tests_passed, result.tests_total), (5, 5))
        self.assertEqual(result.per_test, [True] * 5)
        self.assertIsNone(result.failure_summary)
        self.assertTrue(result.compile_ok)

    def test_fail_summarizes_only_the_first_failing_test(self):
        result, _ = self.run_sandbox(runner.SandboxResult('fail', 3, 5, 40.0, [2, 4], first_failure_actual='4005'))
        self.assertEqual(result.per_test, [True, False, True, False, True])
        self.assertEqual(result.failure_summary,
                         'Test 2 of 5 failed. Inputs: [[2002, 2002]]. Expected: 4004. Got: 4005.')
        self.assertNotIn('4004, 4004', result.failure_summary)  # the second failing case stays hidden

    def test_fail_when_the_call_raised(self):
        result, _ = self.run_sandbox(runner.SandboxResult('fail', 4, 5, 40.0, [1]))
        self.assertEqual(result.failure_summary,
                         'Test 1 of 5 failed. Inputs: [[1001, 1001]]. Expected: 2002. Got: an exception.')

    def test_summary_is_truncated(self):
        huge = json.dumps(list(range(1000)))
        result, _ = self.run_sandbox(runner.SandboxResult('fail', 4, 5, 40.0, [1], first_failure_actual=huge))
        self.assertEqual(len(result.failure_summary), SUMMARY_LIMIT)
        self.assertTrue(result.failure_summary.endswith('...'))

    def test_timeout_oom_and_crash_have_fixed_summaries(self):
        for outcome, expected in (('timeout', 'Execution timed out after 5s.'),
                                  ('oom', 'Execution ran out of memory.'),
                                  ('crash', 'Execution crashed before the tests finished.')):
            result, _ = self.run_sandbox(runner.SandboxResult(outcome, 0, 5, 40.0))
            self.assertEqual(result.exec_outcome, outcome)
            self.assertEqual(result.per_test, [])
            self.assertTrue(result.failure_summary.startswith(expected), result.failure_summary)

    def test_zak_compile_error_is_summarized_without_running(self):
        result, execute = self.run_sandbox(None, source='@solve(a:[I])I{^sum(a)+}', language='zak')
        execute.assert_not_called()
        self.assertEqual(result.exec_outcome, 'not_run')
        self.assertFalse(result.compile_ok)
        self.assertEqual(result.per_test, [])
        error = result.compile_errors[0]
        self.assertEqual(result.failure_summary.splitlines()[0],
                         f"Compile error at {error['line']}:{error['col']}: {error['code']}: {error['message']}")

    def test_python_syntax_error_is_summarized_without_running(self):
        result, execute = self.run_sandbox(None, source='def solve(a) return a')
        execute.assert_not_called()
        self.assertEqual(result.exec_outcome, 'not_run')
        self.assertTrue(result.failure_summary.startswith('Compile error at 1:'))

    def test_zak_transpiled_python_is_returned(self):
        result, execute = self.run_sandbox(runner.SandboxResult('pass', 5, 5, 40.0),
                                           source='@solve(a:[I])I{^sum(a)}', language='zak')
        self.assertIn('def ', execute.call_args.args[0])
        self.assertEqual(result.transpiled_python, execute.call_args.args[0])

    def test_nothing_is_printed(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.run_sandbox(runner.SandboxResult('fail', 4, 5, 40.0, [3], first_failure_actual='0'))
        self.assertEqual((out.getvalue(), err.getvalue()), ('', ''))


if __name__ == '__main__':
    unittest.main()
