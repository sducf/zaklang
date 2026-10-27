"""Tests for public benchmark task loading."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from api.controllers import benchmark
from api.controllers.auth import get_current_user_controller
from api.routes import auth as auth_routes
from api.routes import benchmark as benchmark_routes
from main import app
from database.models import Attempt, Base, BenchmarkRun, Evaluation, User

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class BenchmarkTaskControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_directory.cleanup)
        self.tasks_root = Path(self.temp_directory.name)

        (self.tasks_root / "array_sum").mkdir()
        (self.tasks_root / "array_sum" / "task.json").write_text(
            json.dumps(
                {
                    "id": "array_sum",
                    "title": "Array Sum",
                    "category": "arrays",
                    "prompt": "Return the sum.",
                    "functionName": "solve",
                    "inputs": [{"name": "nums", "type": "integer[]"}],
                    "outputType": "integer",
                }
            ),
            encoding="utf-8",
        )
        # Invalid hidden-test JSON proves task loading does not open this file.
        (self.tasks_root / "array_sum" / "hidden_tests.json").write_text(
            "{not json",
            encoding="utf-8",
        )

        (self.tasks_root / "README.md").write_text("not a task", encoding="utf-8")

    def test_list_reads_public_task_metadata_only(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            tasks = benchmark.list_tasks_controller()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].id, "array_sum")
        self.assertEqual(tasks[0].function_name, "solve")
        self.assertNotIn("hidden_tests", tasks[0].model_dump())

    def test_get_task_maps_fixture_field_names(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            task = benchmark.get_task_controller("array_sum")

        self.assertEqual(task.function_name, "solve")
        self.assertEqual(task.output_type, "integer")
        self.assertEqual(task.inputs[0].name, "nums")

    def test_unknown_task_is_not_found(self):
        with patch.object(benchmark, "TASKS_ROOT", self.tasks_root):
            with self.assertRaises(HTTPException) as raised:
                benchmark.get_task_controller("missing")

        self.assertEqual(raised.exception.status_code, 404)

    def test_compile_invalid_zak_returns_structured_errors(self):
        response = benchmark.compile_controller("@solve(a:[I])I{^sum(a)+}")

        self.assertFalse(response.ok)
        self.assertIsNone(response.python)
        self.assertGreaterEqual(len(response.errors), 1)
        self.assertGreaterEqual(response.errors[0].line, 1)
        self.assertGreaterEqual(response.errors[0].col, 1)
        self.assertTrue(response.errors[0].code)
        self.assertTrue(response.errors[0].message)

    def test_compile_does_not_execute_generated_python(self):
        source = "@solve(a:[I])I{^sum(a)}"
        import sys

        sys.path.insert(0, str(benchmark.REPOSITORY_ROOT))
        from compiler import src

        with patch.object(src, "transpile", return_value="raise RuntimeError"):
            response = benchmark.compile_controller(source)

        self.assertTrue(response.ok)
        self.assertEqual(response.python, "raise RuntimeError")

    def test_task_routes_delegate_to_controllers(self):
        task = benchmark.get_task_controller("array_sum")
        with patch.object(
            benchmark_routes,
            "list_tasks_controller",
            return_value=[task],
        ) as list_controller, patch.object(
            benchmark_routes,
            "get_task_controller",
            return_value=task,
        ) as get_controller:
            self.assertEqual(benchmark_routes.list_tasks(), [task])
            self.assertEqual(benchmark_routes.get_task("array_sum"), task)

        list_controller.assert_called_once_with()
        get_controller.assert_called_once_with("array_sum")


class BenchmarkRunConversionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.session.close)
        self.user = User(email="user@example.com", password_hash="hash")
        self.session.add(self.user)
        self.session.flush()
        self.other_user = User(email="other@example.com", password_hash="hash")
        self.session.add(self.other_user)
        self.session.flush()

    def test_create_queued_run_persists_contract_defaults(self):
        run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.ZAK,
        )

        self.assertIsNotNone(run.id)
        self.assertEqual(run.status, "queued")
        self.assertEqual(run.model_name, "Llama 3.1 8B Instruct")
        self.assertEqual(run.language, "zak")

    def test_run_response_maps_attempt_evaluation_and_totals(self):
        run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.ZAK,
        )
        attempt = Attempt(
            run_id=run.id,
            attempt_number=1,
            prompt_text="prompt",
            generated_code="@solve(a:[I])I{^sum(a)}",
            prompt_tokens=12,
            completion_tokens=5,
            total_tokens=17,
            latency_ms=23.5,
        )
        self.session.add(attempt)
        self.session.flush()
        self.session.add(
            Evaluation(
                attempt_id=attempt.id,
                compile_success=True,
                compiler_output=json.dumps(
                    [{"line": 1, "col": 1, "code": "X", "message": "ok"}]
                ),
                transpiled_code="def solve(a):\n    return sum(a)\n",
                tests_passed=6,
                tests_total=6,
                correct=True,
                exec_outcome="pass",
                execution_ms=10,
            )
        )
        self.session.commit()
        self.session.refresh(run)

        response = benchmark.run_to_response(run)

        self.assertEqual(response.status, benchmark.RunStatus.QUEUED)
        self.assertEqual(response.attempts_used, 1)
        self.assertEqual(response.total_tokens, 17)
        self.assertEqual(response.latency_ms_total, 23.5)
        self.assertEqual(response.attempts[0].exec_outcome, benchmark.ExecutionOutcome.PASS)
        self.assertEqual(response.attempts[0].compile_errors[0].code, "X")

    def test_run_list_item_counts_related_attempts(self):
        run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        self.session.add(
            Attempt(
                run_id=run.id,
                attempt_number=1,
                prompt_text="prompt",
                generated_code="def solve(a): return sum(a)",
            )
        )
        self.session.commit()
        self.session.refresh(run)

        item = benchmark.run_to_list_item(run)

        self.assertEqual(item.language, benchmark.Language.PYTHON)
        self.assertEqual(item.attempts_used, 1)

    def test_create_run_queues_and_schedules_background_work(self):
        class BackgroundTasks:
            def __init__(self):
                self.calls = []

            def add_task(self, function, *args):
                self.calls.append((function, args))

        background_tasks = BackgroundTasks()
        payload = benchmark_routes.RunCreateRequest(
            task_id="array_sum",
            language=benchmark.Language.PYTHON,
            source="def solve(nums): return sum(nums)",
        )

        response = benchmark_routes.create_run(
            payload,
            background_tasks,
            self.user,
            self.session,
        )

        self.assertEqual(response.status, benchmark.RunStatus.QUEUED)
        self.assertEqual(response.attempts, [])
        self.assertEqual(response.model_name, "Llama 3.1 8B Instruct")
        self.assertEqual(len(background_tasks.calls), 1)
        function, args = background_tasks.calls[0]
        self.assertIs(function, benchmark.execute_run_in_background)
        self.assertEqual(args[0], response.id)
        self.assertEqual(args[1:], ("array_sum", benchmark.Language.PYTHON, payload.source))

    def test_run_reads_are_scoped_to_the_current_user(self):
        owned_run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        other_run = benchmark.create_queued_run(
            self.session,
            self.other_user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        self.session.commit()

        listed = benchmark.list_runs_for_user(self.session, self.user)
        owned = benchmark.get_run_for_user(self.session, self.user, owned_run.id)

        self.assertEqual([item.id for item in listed], [owned_run.id])
        self.assertEqual(owned.id, owned_run.id)
        with self.assertRaises(HTTPException) as raised:
            benchmark.get_run_for_user(self.session, self.user, other_run.id)
        self.assertEqual(raised.exception.status_code, 404)

    def test_background_worker_persists_attempts_and_terminal_status(self):
        run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        self.session.commit()
        result = SimpleNamespace(
            exec_outcome="pass",
            attempts=[
                {
                    "number": 1,
                    "prompt": [{"role": "user", "content": "solve"}],
                    "code": "def solve(nums): return sum(nums)",
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "latency_ms": 12,
                    "finish_reason": "stop",
                    "compile_ok": True,
                    "compile_errors": [],
                    "transpiled_python": None,
                    "tests_passed": 6,
                    "tests_total": 6,
                    "exec_outcome": "pass",
                }
            ],
        )

        with patch.object(
            benchmark,
            "SessionLocal",
            side_effect=lambda: sessionmaker(bind=self.engine)(),
        ), \
                patch(
                    "zakbench.runners.run.run_single",
                    return_value=result,
                ) as run_single:
            benchmark.execute_run_in_background(
                run.id,
                "array_sum",
                benchmark.Language.PYTHON,
                "def solve(nums): return sum(nums)",
            )

        run_single.assert_called_once()
        self.session.expire_all()
        saved_run = self.session.get(BenchmarkRun, run.id)
        self.assertEqual(saved_run.status, "passed")
        self.assertIsNotNone(saved_run.completed_at)
        self.assertEqual(len(saved_run.attempts), 1)
        saved_attempt = saved_run.attempts[0]
        self.assertEqual(saved_attempt.total_tokens, 14)
        self.assertEqual(saved_attempt.evaluation.exec_outcome, "pass")
        self.assertEqual(saved_attempt.evaluation.tests_passed, 6)

    def test_background_worker_maps_fail_and_timeout_statuses(self):
        for outcome, expected_status in (("fail", "failed"), ("timeout", "timeout")):
            with self.subTest(outcome=outcome):
                run = benchmark.create_queued_run(
                    self.session,
                    self.user,
                    "array_sum",
                    benchmark.Language.PYTHON,
                )
                self.session.commit()
                result = SimpleNamespace(
                    exec_outcome=outcome,
                    attempts=[
                        {
                            "number": 1,
                            "prompt": None,
                            "code": "def solve(nums): return 0",
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "latency_ms": 1,
                            "finish_reason": None,
                            "compile_ok": True,
                            "compile_errors": [],
                            "transpiled_python": None,
                            "tests_passed": 0,
                            "tests_total": 6,
                            "exec_outcome": outcome,
                        }
                    ],
                )
                with patch.object(
                    benchmark,
                    "SessionLocal",
                    side_effect=lambda: sessionmaker(bind=self.engine)(),
                ), patch(
                    "zakbench.runners.run.run_single",
                    return_value=result,
                ):
                    benchmark.execute_run_in_background(
                        run.id,
                        "array_sum",
                        benchmark.Language.PYTHON,
                        "def solve(nums): return 0",
                    )

                self.session.expire_all()
                self.assertEqual(
                    self.session.get(BenchmarkRun, run.id).status,
                    expected_status,
                )

    def test_background_worker_marks_unexpected_failure_as_error(self):
        run = benchmark.create_queued_run(
            self.session,
            self.user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        self.session.commit()

        with patch.object(
            benchmark,
            "SessionLocal",
            side_effect=lambda: sessionmaker(bind=self.engine)(),
        ), \
                patch(
                    "zakbench.runners.run.run_single",
                    side_effect=RuntimeError("runner unavailable"),
                ), patch.object(benchmark.logger, "exception"):
            benchmark.execute_run_in_background(
                run.id,
                "array_sum",
                benchmark.Language.PYTHON,
                "def solve(nums): return 0",
            )

        self.session.expire_all()
        saved_run = self.session.get(BenchmarkRun, run.id)
        self.assertEqual(saved_run.status, "error")
        self.assertIsNotNone(saved_run.completed_at)
        self.assertEqual(saved_run.attempts, [])


class BenchmarkHttpAuthTests(unittest.TestCase):
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
        self.user = User(email="http-user@example.com", password_hash="hash")
        self.session.add(self.user)
        self.session.commit()

        def override_db():
            db = self.session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[auth_routes.get_db] = override_db
        app.dependency_overrides[benchmark_routes.get_db] = override_db
        self.client = TestClient(app)
        self.addCleanup(app.dependency_overrides.clear)

    def test_runs_require_authentication(self):
        for method, path in (
            ("get", "/runs"),
            ("get", "/runs/1"),
            ("post", "/runs"),
        ):
            with self.subTest(method=method, path=path):
                if method == "post":
                    response = self.client.post(
                        path,
                        json={"task_id": "array_sum", "language": "python"},
                    )
                else:
                    response = self.client.get(path)
                self.assertEqual(response.status_code, 401)

    def test_authenticated_detail_hides_another_users_run(self):
        other_user = User(email="other-http@example.com", password_hash="hash")
        self.session.add(other_user)
        self.session.flush()
        run = benchmark.create_queued_run(
            self.session,
            other_user,
            "array_sum",
            benchmark.Language.PYTHON,
        )
        self.session.commit()

        app.dependency_overrides[get_current_user_controller] = (
            lambda: self.user
        )
        response = self.client.get(
            f"/runs/{run.id}",
            headers={"Authorization": "Bearer test-token"},
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
