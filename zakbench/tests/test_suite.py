"""Tests for matched suite runs and the suite CLI. Inference and Docker are faked; compiling is real.
Run from the repository root: python3 -m unittest discover -s zakbench/tests -t .
"""

import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sandbox import runner
from zakbench.__main__ import main
from zakbench.runners import run, suite
from zakbench.runners.inference import InferenceError
from zakbench.tests.test_run import GOOD_PYTHON, GOOD_ZAK, reply, sandbox

DEFINITION = ('model_id', 'spec_version', 'prompt_version', 'seed', 'temperature', 'max_tokens',
              'max_attempts', 'suite_run_id')


class RunSuiteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def run_suite(self, replies, task_ids=('array_sum', 'palindrome')):
        with patch.object(run, 'generate', side_effect=replies), \
                patch.object(runner, '_execute', return_value=sandbox('pass')):
            return suite.run_suite('dev', 'test-model', 0, '1', '0.1', task_ids=list(task_ids),
                                   results_dir=self.tmp.name)

    def test_two_runs_per_task_share_a_pair_id_and_run_definition(self):
        result = self.run_suite([reply(GOOD_ZAK), reply(GOOD_PYTHON)] * 2)

        self.assertEqual(sorted(path.name for path in result.path.iterdir()), [
            'array_sum-python.json', 'array_sum-zak.json', 'palindrome-python.json', 'palindrome-zak.json',
            'runs.csv', 'summary.json'])
        self.assertEqual(len(result.runs), 4)
        for task_id in ('array_sum', 'palindrome'):
            zak, python = (json.loads((result.path / f'{task_id}-{language}.json').read_text())
                           for language in ('zak', 'python'))
            self.assertEqual(zak['pair_id'], python['pair_id'])
            self.assertEqual(zak['pair_id'], f'{result.suite_run_id}:{task_id}')
            self.assertEqual({field: zak[field] for field in DEFINITION},
                             {field: python[field] for field in DEFINITION})
        self.assertEqual(result.summary['overall']['tasks'], 2)

    def test_runs_csv_has_one_row_per_run(self):
        result = self.run_suite([reply(GOOD_ZAK), reply(GOOD_PYTHON)] * 2)

        with open(result.path / 'runs.csv', newline='', encoding='utf-8') as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(len(rows), 4)
        self.assertEqual(tuple(rows[0]), suite.CSV_COLUMNS)
        first = rows[0]
        self.assertEqual((first['task_id'], first['language'], first['category']), ('array_sum', 'python', 'arrays'))
        self.assertEqual((first['exec_outcome'], first['passed'], first['first_attempt_passed']),
                         ('pass', 'True', 'True'))
        self.assertEqual((first['attempts_used'], first['total_tokens']), ('1', '120'))

    def test_crashed_run_is_recorded_as_error_and_the_suite_continues(self):
        result = self.run_suite([InferenceError('could not reach llama-server'), reply(GOOD_PYTHON),
                                 reply(GOOD_ZAK), reply(GOOD_PYTHON)])

        crashed = json.loads((result.path / 'array_sum-zak.json').read_text())
        self.assertEqual((crashed['exec_outcome'], crashed['passed'], crashed['attempts']), ('error', False, []))
        self.assertEqual(crashed['error'], 'InferenceError: could not reach llama-server')
        self.assertEqual([record['exec_outcome'] for record in result.runs], ['error', 'pass', 'pass', 'pass'])
        self.assertEqual(result.summary['errors'][0]['task_id'], 'array_sum')

    def test_unknown_suite_or_task_is_rejected(self):
        with self.assertRaises(ValueError):
            suite.run_suite('held_out', 'test-model', 0, '1', '0.1', results_dir=self.tmp.name)
        with self.assertRaises(ValueError):
            suite.run_suite('dev', 'test-model', 0, '1', '0.1', task_ids=['nope'], results_dir=self.tmp.name)


class SuiteCliTest(unittest.TestCase):
    def test_suite_run_writes_every_task_and_summarize_reproduces_it(self):
        def fake_generate(messages, **kwargs):
            return reply(GOOD_ZAK if '@' in messages[0]['content'] else GOOD_PYTHON)

        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(run, 'generate', side_effect=fake_generate), \
                patch.object(runner, '_execute', return_value=sandbox('pass')), \
                contextlib.redirect_stdout(io.StringIO()):
            code = main(['run', '--suite', 'dev', '--lang', 'both', '--model', 'test-model', '--seed', '0'],
                        results_dir=tmp)
            [folder] = Path(tmp).iterdir()
            tasks = suite.suite_tasks('dev')
            self.assertEqual(len(list(folder.glob('*-zak.json'))), len(tasks))
            self.assertEqual(len(list(folder.glob('*-python.json'))), len(tasks))
            before = {name: (folder / name).read_bytes() for name in ('summary.json', 'runs.csv')}
            for name in before:
                (folder / name).unlink()

            self.assertEqual(main(['summarize', str(folder)]), 0)
            after = {name: (folder / name).read_bytes() for name in before}
        self.assertEqual(code, 0)
        self.assertEqual(after, before)

    def test_lang_must_match_the_target(self):
        with contextlib.redirect_stderr(io.StringIO()):
            for argv in (['run', '--suite', 'dev', '--lang', 'zak'], ['run', '--task', 'array_sum', '--lang', 'both']):
                with self.assertRaises(SystemExit):
                    main(argv)

    def test_summarize_reports_an_empty_folder(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(main(['summarize', tmp]), 1)
        self.assertIn('no run results', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
