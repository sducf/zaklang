
"""Railway-to-private-sandbox evaluation client."""

import os

import httpx

from zakbench.evaluation.evaluator import EvalResult


_VALID_OUTCOMES = {
    "pass",
    "fail",
    "timeout",
    "oom",
    "crash",
    "not_run",
}


def evaluate_remote(
    source: str,
    task_id: str,
    language: str = "python",
    *,
    timeout_s: float = 5.0,
) -> EvalResult:

    url = os.getenv("SANDBOX_WORKER_URL", "").rstrip("/")
    token = os.getenv("SANDBOX_WORKER_TOKEN", "")

    if not url or not token:
        raise RuntimeError(
            "Sandbox worker is not configured"
        )

    try:
        response = httpx.post(
            f"{url}/evaluate",
            headers={
                "Authorization": f"Bearer {token}"
            },
            json={
                "source": source,
                "task_id": task_id,
                "language": language,
                "timeout_s": timeout_s,
            },
            timeout=timeout_s + 30,
            follow_redirects=False,
            trust_env=False,
        )

        response.raise_for_status()

        payload = response.json()
        result = EvalResult(**payload)

        if (
            result.exec_outcome not in _VALID_OUTCOMES
            or result.tests_total < 0
            or not 0 <= result.tests_passed <= result.tests_total
        ):
            raise ValueError("Invalid sandbox result")

        return result

    except (
        httpx.HTTPError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        raise RuntimeError(
            "Remote sandbox evaluation failed"
        ) from exc
