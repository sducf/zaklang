"""Tests for the SD-60 break-even analysis, against hand-computed values. Run from the repository root:
python3 -m unittest discover -s zakbench/tests -t .
"""

import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

from zakbench.__main__ import main
from zakbench.evaluation.break_even import CSV_COLUMNS, break_even, break_even_rows, size_bins


def make_run(task_id, language, attempts):
    """A stored run record. attempts is (prompt_tokens, completion_tokens, exec_outcome) per attempt."""
    total = sum(prompt + completion for prompt, completion, _ in attempts)
    first = attempts[0][0] + attempts[0][1]
    return {
        'suite': 'dev', 'suite_run_id': 'dev-test', 'pair_id': f'dev-test:{task_id}', 'category': 'arrays',
        'task_id': task_id, 'language': language, 'model_id': 'test-model', 'spec_version': '0.1',
        'prompt_version': '1', 'seed': 0, 'temperature': 0.0, 'max_tokens': 1024, 'max_attempts': 3,
        'exec_outcome': attempts[-1][2], 'passed': attempts[-1][2] == 'pass', 'attempts_used': len(attempts),
        'total_tokens': total, 'repair_tokens': total - first,
        'attempts': [{'prompt_tokens': prompt, 'completion_tokens': completion, 'exec_outcome': outcome}
                     for prompt, completion, outcome in attempts],
    }


# The Zak first prompt is 500 tokens longer than the Python one: that is the spec overhead.
# t2: Zak needs a repair, so its overhead counts twice. t4: Python never passes, so t4 is left out.
RUNS = [
    make_run('t1', 'zak', [(600, 40, 'pass')]),
    make_run('t1', 'python', [(100, 80, 'pass')]),
    make_run('t2', 'zak', [(600, 50, 'fail'), (700, 45, 'pass')]),
    make_run('t2', 'python', [(100, 200, 'pass')]),
    make_run('t3', 'zak', [(600, 100, 'pass')]),
    make_run('t3', 'python', [(100, 400, 'pass')]),
    make_run('t4', 'zak', [(600, 30, 'pass')]),
    make_run('t4', 'python', [(100, 60, 'fail'), (200, 60, 'fail'), (300, 60, 'fail')]),
]


def rows_for(points):
    """Rows with only the fields break_even and size_bins read: (size, measured, without spec)."""
    return [{'size_tokens': size, 'zak_minus_python': measured, 'zak_minus_python_without_spec': without}
            for size, measured, without in points]


class BreakEvenRowsTest(unittest.TestCase):
    def test_one_row_per_paired_task_sorted_by_size(self):
        rows = break_even_rows(RUNS)

        self.assertEqual([(row['task_id'], row['size_tokens'], row['zak_tokens'], row['python_tokens'],
                           row['zak_attempts'], row['spec_tokens'], row['zak_minus_python'],
                           row['zak_minus_python_without_spec']) for row in rows], [
            ('t1', 80, 640, 180, 1, 500, 460, -40),
            ('t2', 200, 1395, 300, 2, 500, 1095, 95),
            ('t3', 400, 700, 500, 1, 500, 200, -300),
        ])

    def test_spec_tokens_replaces_the_measured_overhead(self):
        rows = break_even_rows(RUNS, spec_tokens=400)

        self.assertEqual([row['zak_minus_python_without_spec'] for row in rows], [60, 295, -200])

    def test_incomplete_suite_is_rejected(self):
        with self.assertRaises(ValueError):
            break_even_rows(RUNS[:-1])


class BreakEvenTest(unittest.TestCase):
    def test_crossing_inside_the_size_range(self):
        result = break_even(rows_for([(100, 100, 0), (200, 0, 0), (300, -100, 0)]), 'zak_minus_python')

        self.assertEqual((result['intercept'], result['slope'], result['size']), (200.0, -1.0, 200))
        self.assertEqual(result['statement'],
                         'Zak breaks even at about 200 tokens of task size and uses fewer tokens on larger tasks.')

    def test_crossing_outside_the_range_is_not_a_break_even(self):
        result = break_even(rows_for([(100, 300, 0), (200, 200, 0), (300, 100, 0)]), 'zak_minus_python')

        self.assertIsNone(result['size'])
        self.assertEqual(result['statement'], "No break-even in the dev suite's size range (100 to 300 tokens): "
                                              'Zak uses more tokens across all of it.')

    def test_zak_cheaper_everywhere(self):
        result = break_even(rows_for([(100, 0, -50), (200, 0, -60)]), 'zak_minus_python_without_spec')

        self.assertTrue(result['statement'].endswith('Zak uses fewer tokens across all of it.'))

    def test_one_size_cannot_be_fitted(self):
        result = break_even(rows_for([(100, 5, 5), (100, 7, 7)]), 'zak_minus_python')

        self.assertEqual((result['slope'], result['size']), (None, None))


class SizeBinsTest(unittest.TestCase):
    def test_near_equal_bins_with_mean_differences(self):
        rows = rows_for([(10, 1, -1), (20, 2, -2), (30, 3, -3), (40, 4, -4), (50, 6, -6)])

        self.assertEqual([(b['low'], b['high'], b['tasks'], b['zak_minus_python'],
                           b['zak_minus_python_without_spec']) for b in size_bins(rows)], [
            (10, 10, 1, 1, -1), (20, 20, 1, 2, -2), (30, 30, 1, 3, -3), (40, 50, 2, 5, -5)])


class BreakEvenCommandTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_writes_the_csv_and_prints_the_report(self):
        folder = self.tmp / 'dev-test'
        folder.mkdir()
        for record in RUNS:
            (folder / f"{record['task_id']}-{record['language']}.json").write_text(json.dumps(record))
        out_csv = self.tmp / 'reports' / 'break-even.csv'

        code, out, _ = self.run_main('break-even', str(folder), '--csv', str(out_csv))

        self.assertEqual(code, 0)
        with open(out_csv, newline='', encoding='utf-8') as file:
            rows = list(csv.DictReader(file))
        self.assertEqual(tuple(rows[0]), CSV_COLUMNS)
        self.assertEqual([(row['task_id'], row['size_tokens'], row['zak_minus_python_without_spec'])
                          for row in rows], [('t1', '80', '-40'), ('t2', '200', '95'), ('t3', '400', '-300')])
        self.assertIn('Tasks both languages solved: 3.', out)
        self.assertIn('| 80 to 80 | 1 | 460 | -40 |', out)
        self.assertIn('- Measured (spec included): ', out)
        self.assertIn('- Spec subtracted: ', out)

    def test_empty_folder_is_an_error(self):
        code, _, err = self.run_main('break-even', str(self.tmp))

        self.assertEqual(code, 1)
        self.assertIn('no run results', err)


if __name__ == '__main__':
    unittest.main()
