"""Throwaway test for SD-58. It fails on purpose to show that the sandbox CI job fails. Do not merge."""


def test_sandbox_job_fails_on_a_failing_test():
    assert 1 + 1 == 3, "SD-58 negative check: this test fails on purpose"
