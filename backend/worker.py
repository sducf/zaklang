"""Database-polling benchmark worker for the single GPU deployment."""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from api.controllers.benchmark import execute_run
from api.schemas.benchmark import RunStatus
from database.db import SessionLocal
from database.models import BenchmarkRun

POLL_INTERVAL_SECONDS = 1.0
logger = logging.getLogger(__name__)


def recover_orphaned_runs() -> int:
    """Mark runs left active by a previous worker process as failed."""
    db: Session = SessionLocal()
    try:
        orphaned = (
            db.query(BenchmarkRun)
            .filter(
                BenchmarkRun.status == RunStatus.RUNNING.value,
                BenchmarkRun.suite_run_id.is_(None),
            )
            .all()
        )
        completed_at = datetime.now(timezone.utc)
        for run in orphaned:
            run.status = RunStatus.ERROR.value
            run.completed_at = completed_at
        db.commit()
        if orphaned:
            logger.warning("Marked %s orphaned benchmark runs as error", len(orphaned))
        return len(orphaned)
    except Exception:
        db.rollback()
        logger.exception("Could not recover orphaned benchmark runs")
        raise
    finally:
        db.close()


def claim_next_run() -> int | None:
    """Atomically transition the oldest queued run to running."""
    db: Session = SessionLocal()
    try:
        run = (
            db.query(BenchmarkRun)
            .filter(BenchmarkRun.status == RunStatus.QUEUED.value)
            .order_by(BenchmarkRun.started_at, BenchmarkRun.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if run is None:
            return None
        run.status = RunStatus.RUNNING.value
        db.commit()
        return run.id
    except Exception:
        db.rollback()
        logger.exception("Could not claim the next benchmark run")
        raise
    finally:
        db.close()


def process_next_run() -> bool:
    """Claim and finish one queued run; return whether work was found."""
    run_id = claim_next_run()
    if run_id is None:
        return False
    execute_run(run_id)
    return True


def run_worker(poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Recover previous work, then poll and execute one run at a time."""
    recover_orphaned_runs()
    logger.info("Benchmark worker started")
    while True:
        if not process_next_run():
            time.sleep(poll_interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_worker()
