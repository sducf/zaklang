"""Tests for run metrics. Run from the repository root: python3 -m unittest discover -s zakbench/tests -t ."""

import unittest

from zakbench.evaluation.metrics import Attempt, RunMetrics, compute_run_metrics


class ComputeRunMetricsTest(unittest.TestCase):
    def test_single_passing_attempt_has_no_repair_tokens(self):
        metrics = compute_run_metrics([Attempt(100, 40, 900, True)])
        self.assertEqual(metrics, RunMetrics(
            passed=True, attempts_used=1, prompt_tokens_total=100, completion_tokens_total=40,
            total_tokens=140, first_attempt_tokens=140, repair_tokens=0, latency_ms_total=900))

    def test_repaired_run_counts_every_attempt(self):
        attempts = [Attempt(100, 40, 900, False), Attempt(160, 35, 800, False), Attempt(210, 30, 700, True)]
        metrics = compute_run_metrics(attempts)
        self.assertTrue(metrics.passed)
        self.assertEqual(metrics.attempts_used, 3)
        self.assertEqual((metrics.prompt_tokens_total, metrics.completion_tokens_total), (470, 105))
        self.assertEqual(metrics.total_tokens, 575)
        self.assertEqual(metrics.first_attempt_tokens, 140)
        self.assertEqual(metrics.repair_tokens, 435)
        self.assertEqual(metrics.latency_ms_total, 2400)

    def test_repair_tokens_identity(self):
        for attempts in ([Attempt(5, 5, 1, True)], [Attempt(9, 1, 1, False), Attempt(20, 3, 1, False)]):
            metrics = compute_run_metrics(attempts)
            self.assertEqual(metrics.repair_tokens, metrics.total_tokens - metrics.first_attempt_tokens)

    def test_run_fails_when_last_attempt_fails(self):
        metrics = compute_run_metrics([Attempt(10, 5, 1, False), Attempt(12, 6, 1, False)])
        self.assertFalse(metrics.passed)

    def test_empty_run_is_rejected(self):
        with self.assertRaises(ValueError):
            compute_run_metrics([])


if __name__ == '__main__':
    unittest.main()
