"""SD-83: self-contained Parquet export and DuckDB query tests.

Run from backend/: DATABASE_URL=sqlite:// python -m unittest tests.test_analysis
No GPU, Docker, PostgreSQL, or secrets required.
"""
import contextlib
import io
import json
import os
import sys
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4

import duckdb
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from database.models import Attempt, Base, BenchmarkRun, Evaluation, SuiteRun, User
from zakbench.analysis.export import SCHEMAS, export_suite
from zakbench.analysis.query import analyze


class DuckDBExportTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
        Base.metadata.create_all(self.engine)
        self.addCleanup(self.engine.dispose)
        self.db = sessionmaker(bind=self.engine, expire_on_commit=False)()
        self.addCleanup(self.db.close)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name) / "parquet"

        user = User(email="example@localhost", password_hash="not-real")
        self.db.add(user)
        self.db.flush()
        self.suite = SuiteRun(
            cli_suite_run_id="dev-test", suite="dev", model_name="test-model",
            seed=0, prompt_version="1", spec_version="0.1",
            max_attempts=3, status="completed", user_id=user.id,
        )
        self.db.add(self.suite)
        self.db.flush()

        # One jointly solved pair plus one Python-only task; include repairs,
        # deliberate private text, diagnostic messages, and an error code.
        self.add_run(user.id, "array_sum", "python", "passed",
                     [("pass", 90, 10, [])], self.pair_a)
        self.add_run(user.id, "array_sum", "zak", "passed",
                     [("pass", 100, 20, [])], self.pair_a)
        self.add_run(user.id, "palindrome", "python", "passed",
                     [("fail", 80, 20, []), ("pass", 120, 30, [])], self.pair_b)
        self.add_run(user.id, "palindrome", "zak", "failed",
                     [("not_run", 30, 10, ["SYNTAX_ERROR"]),
                      ("not_run", 30, 10, ["TYPE_MISMATCH"]),
                      ("fail", 30, 10, [])], self.pair_b)
        self.db.commit()

    pair_a = uuid4()
    pair_b = uuid4()

    def add_run(self, user_id, task, language, status, generations, pair):
        run = BenchmarkRun(
            user_id=user_id, suite_run_id=self.suite.id, pair_id=pair,
            task_id=task, category="arrays" if task == "array_sum" else "strings",
            language=language, model_name="test-model", temperature=0.0,
            seed=0, spec_version="0.1", prompt_version="1", max_attempts=3,
            max_tokens=1024, status=status, source="PRIVATE SOURCE",
        )
        self.db.add(run)
        self.db.flush()
        for number, (outcome, prompt, completion, codes) in enumerate(generations, start=1):
            attempt = Attempt(
                run_id=run.id, attempt_number=number,
                prompt_text="HIDDEN_TEST_INPUT_PRIVATE",
                generated_code="EXPECTED_OUTPUT_PRIVATE",
                prompt_tokens=prompt, completion_tokens=completion,
                total_tokens=prompt + completion, latency_ms=10.0,
                finish_reason="stop",
            )
            self.db.add(attempt)
            self.db.flush()
            self.db.add(Evaluation(
                attempt_id=attempt.id, compile_success=not codes,
                compiler_output=json.dumps([
                    {"code": code, "message": "EXPECTED_OUTPUT_PRIVATE"}
                    for code in codes
                ]),
                transpiled_code="EXPECTED_OUTPUT_PRIVATE",
                tests_passed=6 if outcome == "pass" else 0,
                tests_total=6, correct=outcome == "pass",
                exec_outcome=outcome,
            ))

    def test_export_three_parquet_files_and_no_sensitive_columns(self):
        counts = export_suite(self.db, self.suite.id, self.out)
        self.assertEqual(counts, {"suite_runs": 1, "runs": 4, "attempts": 7})
        with duckdb.connect(":memory:") as con:
            for name in counts:
                path = self.out / (name + ".parquet")
                self.assertTrue(path.is_file())
                relation = con.read_parquet(str(path))
                self.assertEqual(relation.count("*").fetchone()[0], counts[name])
                self.assertEqual(set(relation.columns), {field for field, _ in SCHEMAS[name]})
                self.assertFalse(
                    set(relation.columns) & {
                        "prompt_text", "generated_code", "source", "compiler_output",
                        "transpiled_code", "user_id", "hidden_tests", "expected_output",
                    }
                )
            codes = con.execute(
                "SELECT diagnostic_codes FROM read_parquet(?) "
                "WHERE diagnostic_codes != []",
                [str(self.out / "attempts.parquet")],
            ).fetchall()
            self.assertEqual(sorted(value[0][0] for value in codes),
                             ["SYNTAX_ERROR", "TYPE_MISMATCH"])

    def test_duckdb_queries_reproduce_paired_summary_and_repairs(self):
        export_suite(self.db, self.suite.id, self.out)
        old = Path.cwd()
        try:
            os.chdir(self.out)
            with duckdb.connect(":memory:") as con:
                con.execute(
                    (Path(__file__).resolve().parents[2] / "zakbench" /
                     "analysis" / "queries.sql").read_text()
                )
                rows = {
                    x[0]: x
                    for x in con.execute("SELECT * FROM language_metrics").fetchall()
                }
                self.assertEqual(rows["python"][:6], ("python", 2, 2, 0.5, 1.0, 350))
                self.assertEqual(rows["zak"][:6], ("zak", 2, 1, 0.5, 0.5, 240))
                self.assertEqual(rows["python"][7], 175)
                self.assertEqual(rows["zak"][7], 120)
                self.assertEqual(rows["python"][8], round(150 / 350, 4))
                self.assertEqual(rows["zak"][8], round(80 / 240, 4))
                paired = con.execute("SELECT * FROM paired_metrics").fetchone()
                self.assertEqual(paired, (1, 120, 100, 1.2))
        finally:
            os.chdir(old)

        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            analyze(self.out)
        self.assertIn("PAIRED ZAK/PYTHON METRICS", printed.getvalue())
        self.assertIn("ATTEMPT COUNTS", printed.getvalue())

    def test_missing_or_incomplete_suite_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "does not exist"):
            export_suite(self.db, 987654, self.out)
        self.suite.status = "running"
        with self.assertRaisesRegex(ValueError, "not completed"):
            export_suite(self.db, self.suite.id, self.out)
        self.assertFalse(self.out.exists())


if __name__ == "__main__":
    unittest.main()
