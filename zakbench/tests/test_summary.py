"""Tests for suite summary metrics, against hand-computed values. Run from the repository root:
python3 -m unittest discover -s zakbench/tests -t .
"""

import unittest

from zakbench.evaluation.summary import summarize


def make_run(task_id, language, category, outcomes, total_tokens, repair_tokens):
    """A stored run record. outcomes is the exec_outcome of each attempt; None makes an error run."""
    error = outcomes is None
    return {
        'suite': 'dev', 'suite_run_id': 'dev-test', 'pair_id': f'dev-test:{task_id}', 'category': category,
        'task_id': task_id, 'language': language, 'model_id': 'test-model', 'spec_version': '0.1',
        'prompt_version': '1', 'seed': 0, 'temperature': 0.0, 'max_tokens': 1024, 'max_attempts': 3,
        'exec_outcome': 'error' if error else outcomes[-1],
        'passed': not error and outcomes[-1] == 'pass',
        'total_tokens': total_tokens, 'repair_tokens': repair_tokens,
        'attempts': [] if error else [{'exec_outcome': outcome} for outcome in outcomes],
        **({'error': 'RuntimeError: Docker is not available'} if error else {}),
    }


# t1, t2, t5: both solve. t3: only Zak solves. t4: Zak crashes and Python fails, so neither solves.
RUNS = [
    make_run('t1', 'zak', 'arrays', ['pass'], 100, 0),
    make_run('t1', 'python', 'arrays', ['pass'], 200, 0),
    make_run('t2', 'zak', 'arrays', ['fail', 'pass'], 150, 50),
    make_run('t2', 'python', 'arrays', ['pass'], 100, 0),
    make_run('t3', 'zak', 'strings', ['pass'], 80, 0),
    make_run('t3', 'python', 'strings', ['fail', 'fail', 'fail'], 300, 200),
    make_run('t4', 'zak', 'strings', None, 0, 0),
    make_run('t4', 'python', 'strings', ['fail', 'crash', 'fail'], 360, 240),
    make_run('t5', 'zak', 'maps', ['pass'], 60, 0),
    make_run('t5', 'python', 'maps', ['pass'], 90, 0),
]


class SummarizeTest(unittest.TestCase):
    def setUp(self):
        self.summary = summarize(RUNS)
        self.overall = self.summary['overall']

    def test_pass_rates_and_correctness_gap(self):
        zak, python = self.overall['languages']['zak'], self.overall['languages']['python']
        # Zak: first attempt passes t1, t3, t5 (3/5). Within K it also passes t2 (4/5).
        self.assertEqual((zak['pass_at_1'], zak['pass_at_k'], zak['errors']), (0.6, 0.8, 1))
        # Python: t1, t2, t5 pass on the first attempt (3/5), and nothing more within K.
        self.assertEqual((python['pass_at_1'], python['pass_at_k'], python['errors']), (0.6, 0.6, 0))
        self.assertEqual(self.overall['correctness_gap'], 0.2)

    def test_paired_token_stats_use_only_tasks_both_languages_solved(self):
        paired = self.overall['paired']
        self.assertEqual(paired['tasks'], ['t1', 't2', 't5'])
        # Zak tokens [100, 150, 60], Python tokens [200, 100, 90].
        self.assertEqual(paired['zak'], {'mean_total_tokens': 103.3333, 'median_total_tokens': 100})
        self.assertEqual(paired['python'], {'mean_total_tokens': 130, 'median_total_tokens': 100})
        self.assertEqual(paired['token_ratio'], 0.7949)  # 310 / 390
        self.assertEqual(paired['token_ratio_by_task'], {'t1': 0.5, 't2': 1.5, 't5': 0.6667})

    def test_task_solved_only_by_zak_is_listed_and_excluded_from_paired_stats(self):
        self.assertEqual(self.overall['solved_by_zak_only'], ['t3'])
        self.assertEqual(self.overall['solved_by_python_only'], [])
        self.assertEqual(self.overall['solved_by_neither'], ['t4'])
        self.assertNotIn('t3', self.overall['paired']['tasks'])
        self.assertNotIn('t3', self.overall['paired']['token_ratio_by_task'])

    def test_repair_token_share(self):
        self.assertEqual(self.overall['languages']['zak']['repair_token_share'], 0.1282)  # 50 / 390
        self.assertEqual(self.overall['languages']['python']['repair_token_share'], 0.419)  # 440 / 1050

    def test_per_category_breakdown(self):
        self.assertEqual(list(self.summary['by_category']), ['arrays', 'maps', 'strings'])
        strings = self.summary['by_category']['strings']
        self.assertEqual(strings['tasks'], 2)
        self.assertEqual(strings['languages']['zak']['pass_at_k'], 0.5)
        self.assertEqual(strings['languages']['python']['pass_at_k'], 0.0)
        self.assertEqual(strings['paired']['tasks'], [])
        self.assertIsNone(strings['paired']['token_ratio'])
        self.assertIsNone(strings['paired']['zak']['mean_total_tokens'])
        self.assertEqual(self.summary['by_category']['arrays']['paired']['token_ratio'], 0.8333)  # 250 / 300

    def test_error_runs_are_listed(self):
        self.assertEqual(self.summary['errors'],
                         [{'task_id': 't4', 'language': 'zak', 'error': 'RuntimeError: Docker is not available'}])

    def test_run_order_does_not_change_the_summary(self):
        self.assertEqual(summarize(list(reversed(RUNS))), self.summary)

    def test_run_definition_is_recorded(self):
        self.assertEqual((self.summary['model_id'], self.summary['seed'], self.summary['max_attempts']),
                         ('test-model', 0, 3))

    def test_mixed_run_definitions_are_rejected(self):
        other_seed = {**RUNS[1], 'seed': 1}
        with self.assertRaisesRegex(ValueError, 't1 (zak|python): seed is'):
            summarize([RUNS[0], other_seed])

    def test_incomplete_or_duplicate_pairs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 't1: needs one zak run and one python run'):
            summarize(RUNS[:1])
        with self.assertRaisesRegex(ValueError, "t1: unexpected or duplicate 'zak' run"):
            summarize([RUNS[0], RUNS[0], RUNS[1]])
        with self.assertRaises(ValueError):
            summarize([])


if __name__ == '__main__':
    unittest.main()
