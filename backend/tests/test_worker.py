"""Tests for the database-backed single-run worker."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.controllers import benchmark
from api.schemas.benchmark import Language, RunStatus
from database.models import Base, BenchmarkRun, SuiteRun, User
import worker


class BenchmarkWorkerTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = User(email="worker@example.com", password_hash="hash")
        self.db.add(self.user)
        self.db.commit()

    def test_worker_executes_queued_runs_fifo_and_sequentially(self):
        first = benchmark.create_queued_run(
            self.db,
            self.user,
            "array_sum",
            Language.PYTHON,
            source="first",
        )
        second = benchmark.create_queued_run(
            self.db,
            self.user,
            "array_sum",
            Language.PYTHON,
            source="second",
        )
        first.started_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        second.started_at = first.started_at + timedelta(seconds=1)
        self.db.commit()
        events = []

        def fake_run_single(*args, source=None, **kwargs):
            events.append(f"start:{source}")
            events.append(f"finish:{source}")
            return SimpleNamespace(
                exec_outcome="pass",
                temperature=0.0,
                max_tokens=1024,
                attempts=[],
            )

        with patch.object(
            worker,
            "SessionLocal",
            side_effect=self.session_factory,
        ), patch.object(
            benchmark,
            "SessionLocal",
            side_effect=self.session_factory,
        ), patch(
            "zakbench.runners.run.run_single",
            side_effect=fake_run_single,
        ):
            self.assertTrue(worker.process_next_run())
            self.assertTrue(worker.process_next_run())
            self.assertFalse(worker.process_next_run())

        self.assertEqual(
            events,
            ["start:first", "finish:first", "start:second", "finish:second"],
        )
        self.db.expire_all()
        self.assertEqual(self.db.get(BenchmarkRun, first.id).status, "passed")
        self.assertEqual(self.db.get(BenchmarkRun, second.id).status, "passed")

    def test_startup_marks_orphaned_running_runs_as_error(self):
        orphan = benchmark.create_queued_run(
            self.db,
            self.user,
            "array_sum",
            Language.PYTHON,
        )
        orphan.status = RunStatus.RUNNING.value
        queued = benchmark.create_queued_run(
            self.db,
            self.user,
            "array_sum",
            Language.PYTHON,
        )
        suite = SuiteRun(
            cli_suite_run_id="active-suite",
            suite="dev",
            model_name="test-model",
            seed=0,
            prompt_version="1",
            spec_version="0.1",
            max_attempts=3,
            status="running",
            user_id=self.user.id,
        )
        self.db.add(suite)
        self.db.flush()
        suite_run = BenchmarkRun(
            user_id=self.user.id,
            suite_run_id=suite.id,
            task_id="array_sum",
            language="python",
            model_name="test-model",
            seed=0,
            prompt_version="1",
            max_attempts=3,
            status=RunStatus.RUNNING.value,
        )
        self.db.add(suite_run)
        self.db.commit()

        with patch.object(
            worker,
            "SessionLocal",
            side_effect=self.session_factory,
        ):
            recovered = worker.recover_orphaned_runs()

        self.assertEqual(recovered, 1)
        self.db.expire_all()
        self.assertEqual(
            self.db.get(BenchmarkRun, orphan.id).status,
            RunStatus.ERROR.value,
        )
        self.assertIsNotNone(self.db.get(BenchmarkRun, orphan.id).completed_at)
        self.assertEqual(
            self.db.get(BenchmarkRun, queued.id).status,
            RunStatus.QUEUED.value,
        )
        self.assertEqual(
            self.db.get(BenchmarkRun, suite_run.id).status,
            RunStatus.RUNNING.value,
        )


if __name__ == "__main__":
    unittest.main()
