"""Tests for the prompt builder and the single-run repair loop. Inference and Docker are
faked; compiling is real. Run from the repository root:
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
from zakbench.__main__ import main
from zakbench.runners import run
from zakbench.runners.inference import Generation
from zakbench.runners.prompt import TASKS, build_prompt, extract_code, load_task

GOOD_ZAK = '@solve(nums:[I])I{total:=0;~n:nums{total+=n}^total}'
BAD_ZAK = '@solve(nums:[I])I{^sum(nums)+}'
GOOD_PYTHON = 'def solve(nums):\n    return sum(nums)\n'


def reply(text, prompt_tokens=100, completion_tokens=20):
    return Generation(text, prompt_tokens, completion_tokens, 50, 'test-model', 'stop')


def sandbox(outcome, failed=()):
    passed = 6 - len(failed)
    return runner.SandboxResult(outcome, passed, 6, 10.0, list(failed),
                                first_failure_actual='5' if failed else None)


class PromptTest(unittest.TestCase):
    def test_both_languages_get_the_same_task_fields(self):
        task = load_task('binary_search')
        for language in ('zak', 'python'):
            prompt = build_prompt(task, language, '0.1')
            self.assertIn(task['prompt'], prompt)
            self.assertIn('nums: integer[]\ntarget: integer', prompt)
            self.assertNotIn('{{', prompt)
        self.assertIn('@bs(a:[I],t:I)I', build_prompt(task, 'zak', '0.1'))
        self.assertNotIn('@bs', build_prompt(task, 'python', None))

    def test_unknown_spec_version_is_rejected(self):
        with self.assertRaises(ValueError):
            build_prompt(load_task('array_sum'), 'zak', '9.9')

    def test_code_fence_is_removed(self):
        self.assertEqual(extract_code('Here:\n```python\nx = 1\n```\nDone.'), 'x = 1')
        self.assertEqual(extract_code('  x = 1\n'), 'x = 1')


class RunSingleTest(unittest.TestCase):
    def run_loop(self, replies, sandbox_results, language='zak', **kwargs):
        with patch.object(run, 'generate', side_effect=replies) as generate, \
                patch.object(runner, '_execute', side_effect=sandbox_results):
            result = run.run_single('array_sum', language, 'test-model', '0.1', '1', 0, **kwargs)
        return result, generate

    def test_compile_error_is_fed_back_and_repaired(self):
        result, generate = self.run_loop([reply(BAD_ZAK), reply(GOOD_ZAK, 160, 25)], [sandbox('pass')])

        first, second = result.attempts
        self.assertEqual(first['exec_outcome'], 'not_run')
        self.assertFalse(first['compile_ok'])
        error = first['compile_errors'][0]['message']
        second_prompt = generate.call_args_list[1].args[0]
        self.assertEqual(second['prompt'], second_prompt)
        self.assertEqual(second_prompt[1], {'role': 'assistant', 'content': BAD_ZAK})
        self.assertIn(error, second_prompt[2]['content'])
        self.assertTrue(second['compile_ok'])
        self.assertIn("globals()['solve']", second['transpiled_python'])

        self.assertTrue(result.passed)
        self.assertEqual(result.attempts_used, 2)
        self.assertEqual((result.prompt_tokens_total, result.completion_tokens_total), (260, 45))
        self.assertEqual(result.total_tokens, result.prompt_tokens_total + result.completion_tokens_total)
        self.assertEqual(result.repair_tokens, 185)

    def test_stops_after_max_attempts_and_keeps_only_the_bounded_summary(self):
        result, generate = self.run_loop([reply(GOOD_PYTHON)] * 2, [sandbox('fail', [2])] * 2,
                                         language='python', max_attempts=2)

        self.assertEqual(generate.call_count, 2)
        self.assertFalse(result.passed)
        self.assertEqual(result.exec_outcome, 'fail')
        saved = json.dumps(result.__dict__)
        cases = json.loads((TASKS / 'array_sum' / 'hidden_tests.json').read_text())
        self.assertIn('Test 2 of 6 failed. Inputs: [[-2, 5, 1]]. Expected: 4. Got: 5.', saved)
        for case in cases[2:]:  # every case except the summarized one stays out
            self.assertNotIn(json.dumps(case['inputs']), saved)

    def test_given_source_is_evaluated_once_without_generating(self):
        result, generate = self.run_loop([], [sandbox('fail', [1])], source=GOOD_ZAK)

        generate.assert_not_called()
        self.assertEqual(result.attempts_used, 1)
        self.assertEqual(result.total_tokens, 0)
        self.assertIsNone(result.attempts[0]['prompt'])

    def test_cli_writes_a_json_result(self):
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(run, 'generate', return_value=reply(GOOD_PYTHON)), \
                patch.object(runner, '_execute', return_value=sandbox('pass')), \
                contextlib.redirect_stdout(io.StringIO()):
            code = main(['run', '--task', 'array_sum', '--lang', 'python'], results_dir=tmp)
            [path] = Path(tmp).iterdir()
            saved = json.loads(path.read_text())
        self.assertEqual(code, 0)
        self.assertEqual((saved['task_id'], saved['language'], saved['exec_outcome']),
                         ('array_sum', 'python', 'pass'))


if __name__ == '__main__':
    unittest.main()
