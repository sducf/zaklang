"""Per-run metrics from PRD F5: tokens and latency across every attempt, including repairs."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Attempt:
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    passed: bool


@dataclass(frozen=True)
class RunMetrics:
    passed: bool
    attempts_used: int
    prompt_tokens_total: int
    completion_tokens_total: int
    total_tokens: int
    first_attempt_tokens: int
    repair_tokens: int
    latency_ms_total: int


def compute_run_metrics(attempts):
    """Sum a run's attempts, in order. The run passed if its last attempt passed."""
    if not attempts:
        raise ValueError('a run needs at least one attempt')
    prompt_tokens = sum(attempt.prompt_tokens for attempt in attempts)
    completion_tokens = sum(attempt.completion_tokens for attempt in attempts)
    total_tokens = prompt_tokens + completion_tokens
    first_attempt_tokens = attempts[0].prompt_tokens + attempts[0].completion_tokens
    return RunMetrics(
        passed=attempts[-1].passed,
        attempts_used=len(attempts),
        prompt_tokens_total=prompt_tokens,
        completion_tokens_total=completion_tokens,
        total_tokens=total_tokens,
        first_attempt_tokens=first_attempt_tokens,
        repair_tokens=total_tokens - first_attempt_tokens,
        latency_ms_total=sum(attempt.latency_ms for attempt in attempts),
    )
