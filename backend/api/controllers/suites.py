"""Suite runs that the ZakBench CLI stores with --persist, and their summaries."""

from datetime import datetime, timezone
import sys
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.controllers.auth import _normalize_email
from api.controllers.benchmark import REPOSITORY_ROOT, _persist_run_result, get_task_controller
from api.schemas.benchmark import RunStatus, SuiteDetailResponse, SuiteResponse
from database.models import BenchmarkRun, SuiteRun, User


class SuiteStore:
    """Write one CLI suite run, its runs, and their attempts with the API's models and helpers."""

    def __init__(self, db: Session, user_email: str):
        self.db = db
        self.user = db.query(User).filter(User.email == _normalize_email(user_email)).first()
        if self.user is None:
            raise ValueError(f'no user has the email {user_email}')
        self.suite_run: SuiteRun | None = None
        self.pair_ids: dict[str, UUID] = {}

    def start(self, suite, cli_suite_run_id, model_id, seed, prompt_version, spec_version, max_attempts):
        self.suite_run = SuiteRun(
            cli_suite_run_id=cli_suite_run_id, suite=suite, model_name=model_id, seed=seed,
            prompt_version=prompt_version, spec_version=spec_version, max_attempts=max_attempts,
            status='running', user_id=self.user.id)
        self.db.add(self.suite_run)
        self.db.commit()

    def save(self, record: dict[str, Any]) -> None:
        """Store one finished run record from the suite runner. Both runs of a task share a pair_id."""
        pair_id = self.pair_ids.setdefault(record['task_id'], uuid4())
        run = BenchmarkRun(
            user_id=self.user.id, suite_run_id=self.suite_run.id, pair_id=pair_id,
            task_id=record['task_id'], language=record['language'], model_name=record['model_id'],
            temperature=record['temperature'], seed=record['seed'], spec_version=record['spec_version'],
            prompt_version=record['prompt_version'], max_attempts=record['max_attempts'],
            max_tokens=record['max_tokens'], status=RunStatus.RUNNING.value)
        self.db.add(run)
        self.db.flush()
        if record['exec_outcome'] == 'error':
            # The harness crashed, so there are no attempts to store.
            run.status = RunStatus.ERROR.value
            run.completed_at = datetime.now(timezone.utc)
            self.db.commit()
        else:
            _persist_run_result(self.db, run, SimpleNamespace(**record))

    def finish(self, status: str) -> None:
        # Each saved run already committed, so this only drops a write that failed.
        self.db.rollback()
        self.suite_run.status = status
        self.suite_run.finished_at = datetime.now(timezone.utc)
        self.db.commit()


def list_suites(db: Session) -> list[SuiteResponse]:
    """Return every suite run, newest first. Suites are shared results, so any user sees all of them."""
    suites = db.query(SuiteRun).order_by(SuiteRun.created_at.desc(), SuiteRun.id.desc()).all()
    return [SuiteResponse.model_validate(suite, from_attributes=True) for suite in suites]


def get_suite(db: Session, suite_id: int) -> SuiteDetailResponse:
    """Return one suite run and, once it has completed, its summarize() output."""
    suite = db.get(SuiteRun, suite_id)
    if suite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Suite not found')
    summary = None
    if suite.status == 'completed':
        if str(REPOSITORY_ROOT) not in sys.path:
            sys.path.insert(0, str(REPOSITORY_ROOT))
        from zakbench.evaluation.summary import summarize

        summary = summarize([_run_record(suite, run) for run in suite.runs])
    return SuiteDetailResponse(**SuiteResponse.model_validate(suite, from_attributes=True).model_dump(),
                               summary=summary)


def _run_record(suite: SuiteRun, run: BenchmarkRun) -> dict[str, Any]:
    """Rebuild the fields that summarize() reads from a stored run, as the CLI wrote them."""
    attempts = sorted(run.attempts, key=lambda attempt: attempt.attempt_number)
    outcomes = [attempt.evaluation.exec_outcome if attempt.evaluation else None for attempt in attempts]
    totals = [attempt.total_tokens or 0 for attempt in attempts]
    return {
        'suite': suite.suite, 'suite_run_id': suite.cli_suite_run_id, 'model_id': suite.model_name,
        'spec_version': suite.spec_version, 'prompt_version': suite.prompt_version, 'seed': suite.seed,
        'temperature': run.temperature, 'max_tokens': run.max_tokens, 'max_attempts': suite.max_attempts,
        'task_id': run.task_id, 'language': run.language,
        'category': get_task_controller(run.task_id).category,
        # A run with no attempts is a run that crashed the harness.
        'exec_outcome': outcomes[-1] if attempts else 'error',
        'passed': run.status == RunStatus.PASSED.value,
        'total_tokens': sum(totals),
        'repair_tokens': sum(totals) - (totals[0] if totals else 0),
        'attempts': [{'exec_outcome': outcome} for outcome in outcomes],
        # The error text stays in the CLI's run JSON. The database has no column for it.
        'error': None,
    }
