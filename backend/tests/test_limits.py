"""Tests for SD-85: viewer signups, global run caps, auth rate limits and the GPU-down block."""

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api import limits
from api.controllers import benchmark
from api.controllers.auth import get_current_user_controller
from api.routes import auth as auth_routes
from api.routes import benchmark as benchmark_routes
from database.models import Base, BenchmarkRun, SuiteRun, User
from main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
RUN = {"task_id": "array_sum", "language": "python"}
HANDWRITTEN_RUN = {**RUN, "source": "def solve(nums): return sum(nums)"}


class LimitsTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.session = self.session_factory()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)

        def override_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[auth_routes.get_db] = override_db
        app.dependency_overrides[benchmark_routes.get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app)

        limits.reset_rate_limits()
        limits.reset_gpu_cache()
        self.addCleanup(limits.reset_rate_limits)
        self.addCleanup(limits.reset_gpu_cache)

    def add_user(self, email: str, role: str | None = None) -> User:
        user = User(email=email, password_hash="hash")
        if role is not None:
            user.role = role
        self.session.add(user)
        self.session.commit()
        return user

    def act_as(self, user: User) -> None:
        app.dependency_overrides[get_current_user_controller] = lambda: user

    def add_runs(
        self,
        user: User,
        count: int,
        status: str = "queued",
        started_at: datetime | None = None,
        suite_run_id: int | None = None,
    ) -> None:
        for _ in range(count):
            run = benchmark.create_queued_run(
                self.session, user, "array_sum", benchmark.Language.PYTHON
            )
            run.status = status
            run.suite_run_id = suite_run_id
            if started_at is not None:
                run.started_at = started_at
        self.session.commit()

    def run_count(self) -> int:
        return self.session.query(func.count(BenchmarkRun.id)).scalar()


class ViewerSignupTests(LimitsTestCase):
    def test_new_signup_is_stored_as_viewer(self):
        response = self.client.post(
            "/auth/register",
            json={"email": "new@example.com", "password": "long-enough-password"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["role"], "viewer")
        stored = self.session.query(User).filter_by(email="new@example.com").one()
        self.assertEqual(stored.role, "viewer")

    def test_viewer_still_gets_403_on_matched_run_launch(self):
        self.act_as(self.add_user("viewer@example.com"))

        response = self.client.post("/runs/pair", json={"task_id": "array_sum"})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.run_count(), 0)


class MigrationTests(unittest.TestCase):
    def test_migration_sets_viewer_server_default_and_keeps_existing_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "schema.db"
            url = f"sqlite:///{database}"
            config = Config(str(BACKEND_ROOT / "alembic.ini"))
            config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))

            with patch.dict(os.environ, {"DATABASE_URL": url}):
                config.set_main_option("sqlalchemy.url", url)
                command.upgrade(config, "d24b8c6f1a03")
                with sqlite3.connect(database) as connection:
                    connection.execute(
                        "INSERT INTO users (id, email, password_hash, role, created_at) "
                        "VALUES ('a', 'member@example.com', 'hash', 'member', '2026-11-01')"
                    )
                command.upgrade(config, "head")

            with sqlite3.connect(database) as connection:
                connection.execute(
                    "INSERT INTO users (id, email, password_hash, created_at) "
                    "VALUES ('b', 'new@example.com', 'hash', '2026-11-24')"
                )
                roles = dict(connection.execute("SELECT email, role FROM users"))

        self.assertEqual(
            roles,
            {"member@example.com": "member", "new@example.com": "viewer"},
        )


@patch.dict(os.environ, {"RUN_QUEUE_CAP": "3", "DAILY_RUN_CAP": "100"})
class QueueCapTests(LimitsTestCase):
    def setUp(self):
        super().setUp()
        self.member = self.add_user("member@example.com", "member")
        self.act_as(self.member)

    def test_run_at_queue_cap_is_rejected_without_adding_a_row(self):
        self.add_runs(self.member, 3)

        response = self.client.post("/runs", json=RUN)

        self.assertEqual(response.status_code, 429)
        self.assertIn("queue is full", response.json()["detail"])
        self.assertEqual(self.run_count(), 3)

    def test_pair_that_would_pass_the_cap_is_rejected_without_adding_rows(self):
        self.add_runs(self.member, 2)

        response = self.client.post("/runs/pair", json={"task_id": "array_sum"})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.run_count(), 2)

    def test_finished_runs_do_not_count_toward_the_queue(self):
        self.add_runs(self.member, 2)
        self.add_runs(self.member, 5, status="passed")

        response = self.client.post("/runs", json=RUN)

        self.assertEqual(response.status_code, 202)


@patch.dict(os.environ, {"RUN_QUEUE_CAP": "100", "DAILY_RUN_CAP": "3"})
class DailyCapTests(LimitsTestCase):
    def test_daily_cap_rejects_every_role_once_reached(self):
        owner = self.add_user("owner@example.com", "member")
        self.add_runs(owner, 3, status="passed")

        for role in ("admin", "member", "viewer"):
            with self.subTest(role=role):
                self.act_as(self.add_user(f"{role}@example.com", role))
                response = self.client.post("/runs", json=RUN)
                self.assertEqual(response.status_code, 429)
                self.assertIn("runs per day", response.json()["detail"])
                self.assertIn("resets at", response.json()["detail"])

        self.act_as(self.add_user("pair-admin@example.com", "admin"))
        response = self.client.post("/runs/pair", json={"task_id": "array_sum"})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(self.run_count(), 3)

    def test_yesterdays_runs_and_suite_runs_do_not_count(self):
        admin = self.add_user("admin@example.com", "admin")
        self.add_runs(
            admin,
            5,
            status="passed",
            started_at=datetime.now(timezone.utc) - timedelta(days=1, hours=1),
        )
        suite = SuiteRun(
            cli_suite_run_id="dev-sd85",
            suite="dev",
            model_name=benchmark.MODEL_NAME,
            seed=0,
            prompt_version="1",
            max_attempts=3,
            user_id=admin.id,
        )
        self.session.add(suite)
        self.session.commit()
        self.add_runs(admin, 5, status="passed", suite_run_id=suite.id)
        self.act_as(admin)

        response = self.client.post("/runs/pair", json={"task_id": "array_sum"})

        self.assertEqual(response.status_code, 202)


class RateLimitTests(LimitsTestCase):
    def test_eleventh_login_from_one_ip_in_a_minute_is_rejected(self):
        body = {"email": "nobody@example.com", "password": "wrong-password"}
        codes = [
            self.client.post("/auth/login", json=body).status_code
            for _ in range(10)
        ]
        rejected = self.client.post("/auth/login", json=body)

        self.assertEqual(codes, [401] * 10)
        self.assertEqual(rejected.status_code, 429)
        self.assertIn("Retry-After", rejected.headers)

    def test_eleventh_signup_from_one_ip_in_a_minute_is_rejected(self):
        codes = [
            self.client.post(
                "/auth/register",
                json={"email": f"user{index}@example.com", "password": "long-enough-password"},
            ).status_code
            for index in range(11)
        ]

        self.assertEqual(codes, [201] * 10 + [429])

    def test_limit_is_per_client_ip(self):
        body = {"email": "nobody@example.com", "password": "wrong-password"}
        for _ in range(10):
            self.client.post("/auth/login", json=body, headers={"X-Real-IP": "203.0.113.1"})

        blocked = self.client.post(
            "/auth/login", json=body, headers={"X-Real-IP": "203.0.113.1"}
        )
        other = self.client.post(
            "/auth/login", json=body, headers={"X-Real-IP": "203.0.113.2"}
        )

        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(other.status_code, 401)


class GpuDownTests(LimitsTestCase):
    def setUp(self):
        super().setUp()
        self.act_as(self.add_user("member@example.com", "member"))

    def test_handwritten_run_is_rejected_while_gpu_is_down(self):
        with patch.object(limits, "gpu_is_available", return_value=False):
            response = self.client.post("/runs", json=HANDWRITTEN_RUN)

        self.assertEqual(response.status_code, 503)
        self.assertIn("GPU is offline", response.json()["detail"])
        self.assertEqual(self.run_count(), 0)

    def test_model_run_is_not_blocked_by_the_gpu_check(self):
        with patch.object(limits, "gpu_is_available", return_value=False):
            response = self.client.post("/runs", json=RUN)

        self.assertEqual(response.status_code, 202)

    def test_handwritten_run_is_accepted_while_gpu_is_up(self):
        with patch.object(limits, "gpu_is_available", return_value=True):
            response = self.client.post("/runs", json=HANDWRITTEN_RUN)

        self.assertEqual(response.status_code, 202)

    def test_unset_gpu_url_counts_as_down(self):
        with patch.dict(os.environ, {"GPU_API_URL": ""}):
            self.assertFalse(limits.gpu_is_available())

    def test_health_result_is_cached(self):
        with patch.dict(os.environ, {"GPU_API_URL": "http://gpu.invalid"}), patch.object(
            limits.httpx, "get"
        ) as get:
            get.return_value.is_success = True
            self.assertTrue(limits.gpu_is_available())
            self.assertTrue(limits.gpu_is_available())

        self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main()
