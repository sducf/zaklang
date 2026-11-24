# ZakBench Parquet + DuckDB analysis (SD-83)

This is an offline, read-only export from Railway PostgreSQL (the system of
record). It does **not** replace Postgres, deploy a new Railway service, change
the database schema, or run inference. It works with any completed persisted
suite, including the SD-59 baseline (database suite ID 9) and future v0.2 runs.

## Install and run

The normal Backend Docker image installs duckdb from backend/requirements.txt.
It uses the same DATABASE_URL environment variable as the suite runner.

SSH into the existing Railway Backend:

    railway ssh --service Backend --environment production

Inside the SSH shell, after the SD-83 branch has merged and the Backend has
deployed its updated image:

    cd /app
    python -m zakbench.analysis.export --suite-id 9 --out zakbench/results/parquet/suite-9

Expected files, each containing a single suite:

    zakbench/results/parquet/suite-9/suite_runs.parquet
    zakbench/results/parquet/suite-9/runs.parquet
    zakbench/results/parquet/suite-9/attempts.parquet

To reproduce the summary from **those Parquet files**, without querying
PostgreSQL again:

    python -m zakbench.analysis.query --dir zakbench/results/parquet/suite-9

The query runner loads queries.sql into an in-memory DuckDB connection. It
prints four tables: per-language metrics, per-category solved counts, paired
Zak/Python token totals and ratio, and total attempts by language. If using
the DuckDB CLI instead, change your working directory to the export folder
and run the SQL file with the CLI's .read command.

**Expected validation for suite 9:**

- runs.parquet: 100 rows (50 Zak, 50 Python)
- attempts.parquet: 140 Zak attempt rows (SD-61 acceptance reference)
- Python: 47 / 50 solved; pass@1 0.84; pass@3 0.94; total tokens 15,642;
  mean 312.84; median 208.5; repair-token share 0.3461
- Zak: 6 / 50 solved; pass@1 0.08; pass@3 0.12; total tokens 168,904;
  mean 3378.08; median 3284.5; repair-token share 0.7012
- Paired Zak / Python token ratio on six jointly solved tasks: 8.4633

These are the expected figures from dev-baseline-v0.1.md, not a claim that
this export has been run on production yet. Check the CLI's actual output.

## Output schemas

- suite_runs.parquet: suite ID, CLI suite ID, suite, model, seed, prompt/spec
  versions, attempt limit, status and timestamps. No user ID.
- runs.parquet: run/suite/pair IDs, task, category, language, model and settings,
  status and correctness, first-pass flag, attempt count, prompt/completion/
  total/first/repair tokens, latency, and final tests-passed/total counts.
- attempts.parquet: attempt/run IDs, attempt index, prompt/completion/total
  token counts, latency, compile success, diagnostic error codes only,
  execution outcome, finish reason.

We intentionally do **not** export users, prompts, generated source code,
compiler messages, transpiled code, test inputs, hidden test files, expected
outputs, or raw execution reports. Diagnostic error codes are safe to count
without leaking source snippets.

## Privacy and storage

By default, the exporter writes beneath zakbench/results/parquet/suite-<id>.
The repository already ignores everything under zakbench/results/*, except
.gitkeep. Do not commit Parquet outputs or raw benchmark result JSON to GitHub.

Railway service filesystems may be replaced on deploy/restart. If the team
needs to keep exports longer term, transfer them into private, authorized
storage. Regenerate using the command above at any time while PostgreSQL
retains the suite.

## Testing (no PostgreSQL or GPU)

From the repository root, after dependencies are installed:

    cd backend
    DATABASE_URL=sqlite:// python -m unittest tests.test_analysis
    DATABASE_URL=sqlite:// python -m unittest discover -s tests

The test uses SQLite in memory and an isolated temporary Parquet folder.
It checks the exported tables, column allowlists, aggregate calculations,
paired token ratio and exclusions for sensitive source/test data.
