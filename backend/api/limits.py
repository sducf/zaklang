"""Site-wide limits that protect the shared GPU and the paid sandbox."""

import math
import os
import threading
import time as clock
from collections import defaultdict, deque
from datetime import datetime, time, timedelta, timezone

import httpx
from fastapi import HTTPException, Request, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from api.schemas.benchmark import RunStatus
from database.models import BenchmarkRun

DEFAULT_RUN_QUEUE_CAP = 50
DEFAULT_DAILY_RUN_CAP = 200
DEFAULT_AUTH_RATE_LIMIT_PER_MINUTE = 10
RATE_LIMIT_WINDOW_SECONDS = 60
GPU_HEALTH_TIMEOUT_SECONDS = 3.0
GPU_HEALTH_CACHE_SECONDS = 30.0
# Any constant works; it only has to be the same for every run-creating request.
RUN_CREATION_LOCK_KEY = 85


def int_setting(name: str, default: int) -> int:
    """Read a positive integer setting at call time so tests and deploys can change it."""
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def client_ip(request: Request) -> str:
    """Return the caller's IP. Railway's edge sets X-Real-IP and replaces any client copy."""
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


_rate_limit_lock = threading.Lock()
_rate_limit_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def reset_rate_limits() -> None:
    """Forget every recorded request. Used by tests."""
    with _rate_limit_lock:
        _rate_limit_hits.clear()


def rate_limit(bucket: str):
    """Build a dependency that allows a limited number of requests per IP per minute."""

    def dependency(request: Request) -> None:
        limit = int_setting(
            "AUTH_RATE_LIMIT_PER_MINUTE",
            DEFAULT_AUTH_RATE_LIMIT_PER_MINUTE,
        )
        now = clock.monotonic()
        window_start = now - RATE_LIMIT_WINDOW_SECONDS
        key = (bucket, client_ip(request))
        with _rate_limit_lock:
            hits = _rate_limit_hits[key]
            while hits and hits[0] <= window_start:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = max(
                    1,
                    math.ceil(hits[0] + RATE_LIMIT_WINDOW_SECONDS - now),
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Too many requests. "
                        f"Try again in {retry_after} seconds."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            hits.append(now)
            # Drop idle keys so the store does not grow with every IP ever seen.
            for stale_key in [
                other
                for other, other_hits in _rate_limit_hits.items()
                if not other_hits or other_hits[-1] <= window_start
            ]:
                del _rate_limit_hits[stale_key]

    return dependency


def lock_run_creation(db: Session) -> None:
    """Serialize run creation on PostgreSQL so concurrent requests cannot pass a cap together."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": RUN_CREATION_LOCK_KEY},
        )


def enforce_global_run_caps(
    db: Session,
    new_runs: int,
    now: datetime | None = None,
) -> None:
    """Reject new API runs once the daily cap or the queue cap would be exceeded."""
    current_time = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day_start = datetime.combine(current_time.date(), time.min, timezone.utc)
    day_end = day_start + timedelta(days=1)

    daily_cap = int_setting("DAILY_RUN_CAP", DEFAULT_DAILY_RUN_CAP)
    runs_today = (
        db.query(func.count(BenchmarkRun.id))
        .filter(
            BenchmarkRun.suite_run_id.is_(None),
            BenchmarkRun.started_at >= day_start,
            BenchmarkRun.started_at < day_end,
        )
        .scalar()
    )
    if runs_today + new_runs > daily_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"The site-wide limit of {daily_cap} runs per day has been "
                f"reached. It resets at {day_end.isoformat()}."
            ),
        )

    queue_cap = int_setting("RUN_QUEUE_CAP", DEFAULT_RUN_QUEUE_CAP)
    queued = (
        db.query(func.count(BenchmarkRun.id))
        .filter(BenchmarkRun.status == RunStatus.QUEUED.value)
        .scalar()
    )
    if queued + new_runs > queue_cap:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"The run queue is full ({queue_cap} runs waiting). "
                "Try again in a few minutes."
            ),
        )


_gpu_lock = threading.Lock()
_gpu_cache: dict[str, float | bool] = {}


def reset_gpu_cache() -> None:
    """Forget the cached GPU health result. Used by tests."""
    with _gpu_lock:
        _gpu_cache.clear()


def gpu_is_available() -> bool:
    """Return whether llama.cpp answers its health check, caching the answer briefly."""
    base_url = os.getenv("GPU_API_URL", "").rstrip("/")
    if not base_url:
        return False

    now = clock.monotonic()
    with _gpu_lock:
        checked_at = _gpu_cache.get("checked_at")
        if checked_at is not None and now - checked_at < GPU_HEALTH_CACHE_SECONDS:
            return bool(_gpu_cache["available"])

    try:
        response = httpx.get(
            f"{base_url}/health",
            timeout=GPU_HEALTH_TIMEOUT_SECONDS,
        )
        available = response.is_success
    except httpx.HTTPError:
        available = False

    with _gpu_lock:
        _gpu_cache["checked_at"] = now
        _gpu_cache["available"] = available
    return available


def require_gpu_for_handwritten() -> None:
    """Stop hand-written runs, which skip the model but still use the sandbox, while the GPU is off."""
    if not gpu_is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Hand-written runs are paused while the GPU is offline. "
                "Try again later."
            ),
        )
