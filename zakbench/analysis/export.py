"""Export a persisted ZakBench suite from PostgreSQL to privacy-safe Parquet.

The PostgreSQL database remains the system of record. Only explicitly selected
analysis columns are exported; prompts, generated code, and test contents are
never read into the Parquet files.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

# Explicit allowlists: do not accidentally export model/source/test text.
SCHEMAS = {
    "suite_runs": [
        ("suite_id", "BIGINT"),
        ("cli_suite_run_id", "VARCHAR"),
        ("suite", "VARCHAR"),
        ("model_id", "VARCHAR"),
        ("seed", "INTEGER"),
        ("prompt_version", "VARCHAR"),
        ("spec_version", "VARCHAR"),
        ("max_attempts", "INTEGER"),
        ("status", "VARCHAR"),
        ("created_at", "TIMESTAMPTZ"),
        ("finished_at", "TIMESTAMPTZ"),
    ],
    "runs": [
        ("run_id", "BIGINT"),
        ("suite_id", "BIGINT"),
        ("pair_id", "VARCHAR"),
        ("task_id", "VARCHAR"),
        ("category", "VARCHAR"),
        ("language", "VARCHAR"),
        ("model_id", "VARCHAR"),
        ("spec_version", "VARCHAR"),
        ("prompt_version", "VARCHAR"),
        ("seed", "INTEGER"),
        ("temperature", "DOUBLE"),
        ("max_attempts", "INTEGER"),
        ("status", "VARCHAR"),
        ("passed", "BOOLEAN"),
        ("first_attempt_passed", "BOOLEAN"),
        ("attempts_used", "INTEGER"),
        ("prompt_tokens_total", "BIGINT"),
        ("completion_tokens_total", "BIGINT"),
        ("total_tokens", "BIGINT"),
        ("first_attempt_tokens", "BIGINT"),
        ("repair_tokens", "BIGINT"),
        ("latency_ms_total", "DOUBLE"),
        ("tests_passed", "INTEGER"),
        ("tests_total", "INTEGER"),
    ],
    "attempts": [
        ("attempt_id", "BIGINT"),
        ("run_id", "BIGINT"),
        ("attempt_index", "INTEGER"),
        ("prompt_tokens", "BIGINT"),
        ("completion_tokens", "BIGINT"),
        ("total_tokens", "BIGINT"),
        ("latency_ms", "DOUBLE"),
        ("compile_ok", "BOOLEAN"),
        ("diagnostic_codes", "VARCHAR[]"),
        ("exec_outcome", "VARCHAR"),
        ("finish_reason", "VARCHAR"),
    ],
}


def _diagnostic_codes(value: str | None) -> list[str]:
    """Extract *only* compiler error codes, not messages or source snippets."""
    if not value:
        return []
    try:
        errors = json.loads(value)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid stored compiler diagnostics JSON") from error
    if not isinstance(errors, list):
        raise ValueError("stored compiler diagnostics must be an array")
    return [str(item["code"]) for item in errors
            if isinstance(item, dict) and isinstance(item.get("code"), str)]


def export_suite(db, suite_id: int, out: Path) -> dict[str, int]:
    """Read one completed suite using the application's existing ORM session.

    This function is read-only with respect to PostgreSQL, and accepts a
    SQLAlchemy Session so it can be tested with an in-memory SQLite database.
    """
    from sqlalchemy.orm import joinedload
    from database.models import Attempt, BenchmarkRun, SuiteRun

    suite = db.get(SuiteRun, suite_id)
    if suite is None:
        raise ValueError(f"suite {suite_id} does not exist")
    if suite.status != "completed":
        raise ValueError(f"suite {suite_id} is {suite.status!r}, not completed")

    runs = (db.query(BenchmarkRun)
            .filter(BenchmarkRun.suite_run_id == suite_id)
            .order_by(BenchmarkRun.id)
            .all())
    if not runs:
        raise ValueError(f"suite {suite_id} has no benchmark runs")

    attempt_records = (db.query(Attempt)
                       .options(joinedload(Attempt.evaluation))
                       .filter(Attempt.run_id.in_([run.id for run in runs]))
                       .order_by(Attempt.run_id, Attempt.attempt_number)
                       .all())
    by_run = defaultdict(list)
    for attempt in attempt_records:
        by_run[attempt.run_id].append(attempt)

    suite_rows = [(
        suite.id, suite.cli_suite_run_id, suite.suite, suite.model_name,
        suite.seed, suite.prompt_version, suite.spec_version,
        suite.max_attempts, suite.status, suite.created_at, suite.finished_at,
    )]
    run_rows = []
    attempt_rows = []
    for run in runs:
        attempts = by_run[run.id]
        prompt_tokens = sum(a.prompt_tokens or 0 for a in attempts)
        completion_tokens = sum(a.completion_tokens or 0 for a in attempts)
        total_tokens = sum(
            a.total_tokens if a.total_tokens is not None
            else (a.prompt_tokens or 0) + (a.completion_tokens or 0)
            for a in attempts
        )
        first_attempt_tokens = (
            (attempts[0].total_tokens if attempts[0].total_tokens is not None
             else (attempts[0].prompt_tokens or 0) +
                  (attempts[0].completion_tokens or 0))
            if attempts else 0
        )
        last_evaluation = attempts[-1].evaluation if attempts else None
        first_pass = bool(
            attempts and attempts[0].evaluation
            and attempts[0].evaluation.exec_outcome == "pass"
        )
        run_rows.append((
            run.id, suite_id, str(run.pair_id) if run.pair_id else None,
            run.task_id, run.category, run.language, run.model_name,
            run.spec_version, run.prompt_version, run.seed, run.temperature,
            run.max_attempts, run.status, run.status == "passed", first_pass,
            len(attempts), prompt_tokens, completion_tokens, total_tokens,
            first_attempt_tokens, total_tokens - first_attempt_tokens,
            sum(a.latency_ms or 0 for a in attempts),
            last_evaluation.tests_passed if last_evaluation else None,
            last_evaluation.tests_total if last_evaluation else None,
        ))
        for attempt in attempts:
            evaluation = attempt.evaluation
            attempt_rows.append((
                attempt.id, run.id, attempt.attempt_number,
                attempt.prompt_tokens, attempt.completion_tokens,
                attempt.total_tokens, attempt.latency_ms,
                evaluation.compile_success if evaluation else None,
                _diagnostic_codes(evaluation.compiler_output) if evaluation else [],
                evaluation.exec_outcome if evaluation else None,
                attempt.finish_reason,
            ))

    tables = {
        "suite_runs": suite_rows,
        "runs": run_rows,
        "attempts": attempt_rows,
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(":memory:")
    try:
        for name, fields in SCHEMAS.items():
            ddl = ", ".join(f"{column} {dtype}" for column, dtype in fields)
            con.execute(f"CREATE TABLE {name} ({ddl})")
            data = tables[name]
            if data:
                placeholders = ", ".join("?" for _ in fields)
                con.executemany(f"INSERT INTO {name} VALUES ({placeholders})", data)
            # SQL-quote the output path; only fixed, allowlisted table names are used.
            destination = str((out / f"{name}.parquet").resolve()).replace("'", "''")
            con.execute(f"COPY {name} TO '{destination}' (FORMAT PARQUET)")
    finally:
        con.close()
    return {name: len(rows) for name, rows in tables.items()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", type=int, required=True)
    parser.add_argument("--out", type=Path,
                        help="Default: zakbench/results/parquet/suite-<id>")
    args = parser.parse_args(argv)

    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from database.db import SessionLocal

    out = args.out or ROOT / "zakbench" / "results" / "parquet" / f"suite-{args.suite_id}"
    try:
        with SessionLocal() as db:
            counts = export_suite(db, args.suite_id, out)
    except (ValueError, OSError) as error:
        parser.exit(1, f"export failed: {error}\n")

    print(f"Exported suite {args.suite_id} to {out}")
    for filename, count in counts.items():
        print(f"  {filename}.parquet: {count} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
