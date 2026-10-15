# ZakLang Backend

The ZakLang backend is built with FastAPI and uses PostgreSQL for persistent application and benchmark data.

## Database

ZakLang uses SQLAlchemy for database models and Alembic for schema migrations.

The main database models are defined in:

```text
database/models.py
```

The current schema includes:

- `users`
- `benchmark_runs`
- `attempts`
- `evaluations`

## API Layout

FastAPI route modules live under `api/routes/`:

- `api/routes/testing.py` contains the root and GPU connectivity routes.
- `api/routes/auth.py` contains the registration, login, token refresh, and
  current-user endpoints. Login and refresh return a short-lived access token
  and a longer-lived refresh token (`REFRESH_TOKEN_EXPIRE_DAYS`, default 7).
  Send the refresh token to `POST /auth/refresh` to get a new pair.
- `api/controllers/` contains route-adjacent application behavior. The GPU
  health controller is the first extracted implementation; auth controllers
  will be added with the authentication service.
- `main.py` only creates the application, configures CORS, and registers
  routers. Database access and authentication services should be added behind
  the route layer rather than directly in `main.py`.

A human-readable DBML representation of the schema is available at:

```text
database/schema.dbml
```

The DBML file can be opened in tools such as dbdiagram.io to visualize tables, columns, constraints, and relationships.

The SQLAlchemy models remain the application source of truth.

## Database Relationships

A benchmark run can contain multiple generation attempts:

```text
benchmark_runs 1 ---- many attempts
```

From the opposite direction, many attempts belong to one benchmark run.

Each attempt can have at most one evaluation:

```text
attempts 1 ---- 0..1 evaluations
```

User accounts are stored separately in the `users` table.

## Environment Variables

Database credentials must not be committed to the repository.

For local development, `python-dotenv` loads variables from `backend/.env`.
Production variables supplied by Railway take precedence because the loader
does not override existing process environment variables. The local file uses
SQLite by default, so a local PostgreSQL server is not required.

Install dependencies from the `backend/` directory (virtual env active):

```bash
pip install -r requirements.txt
```

Start the API locally:

```bash
uvicorn main:app --reload
```

Open the API documentation at `http://127.0.0.1:8000/docs`.

## Benchmark API Contract

The benchmark routes are contract-only stubs and appear in FastAPI docs with
their request and response models. Endpoint behavior is implemented separately.

`GET /runs/{id}` returns a run aggregate. Token counts and latency are totals
across attempts; test counts belong to the individual attempt that produced
them and are not summed at run level:

```json
{
  "id": 42,
  "task_id": "array_sum",
  "language": "zak",
  "model_name": "Llama 3.1 8B Instruct",
  "temperature": 0.2,
  "started_at": "2026-10-15T12:00:00Z",
  "completed_at": "2026-10-15T12:00:04Z",
  "status": "passed",
  "attempts_used": 2,
  "prompt_tokens_total": 2200,
  "completion_tokens_total": 74,
  "total_tokens": 2274,
  "latency_ms_total": 4210,
  "attempts": [
    {
      "index": 1,
      "completion_text": "generated Zak source",
      "prompt_tokens": 1100,
      "completion_tokens": 36,
      "total_tokens": 1136,
      "latency_ms": 2140,
      "compile_ok": false,
      "compile_errors": [
        { "line": 4, "col": 8, "code": "E001", "message": "Unexpected token" }
      ],
      "transpiled_python": null,
      "tests_passed": null,
      "tests_total": null,
      "exec_outcome": "not_run"
    },
    {
      "index": 2,
      "completion_text": "def solve(nums):\n    return sum(nums)",
      "prompt_tokens": 1100,
      "completion_tokens": 38,
      "total_tokens": 1138,
      "latency_ms": 2070,
      "compile_ok": true,
      "compile_errors": [],
      "transpiled_python": "def solve(nums):\\n    return sum(nums)",
      "tests_passed": 3,
      "tests_total": 3,
      "exec_outcome": "pass"
    }
  ]
}
```

The backend and Alembic read the database connection from:

```text
DATABASE_URL
```

Railway provides this environment variable for the deployed PostgreSQL database.

Railway PostgreSQL URLs beginning with:

```text
postgresql://
```

are converted to:

```text
postgresql+psycopg://
```

so SQLAlchemy uses the psycopg PostgreSQL driver.

## Database Migrations

Alembic manages changes to the PostgreSQL schema.

All Alembic commands require `DATABASE_URL` to be set.

Run Alembic commands from the `backend/` directory.

### Apply All Migrations

```bash
python -m alembic upgrade head
```

### View the Current Migration

```bash
python -m alembic current
```

### View Migration History

```bash
python -m alembic history
```

### Roll Back All Migrations

```bash
python -m alembic downgrade base
```

This should only be used when intentionally removing the migrated schema.

### Create a New Migration

After modifying the SQLAlchemy models:

```bash
python -m alembic revision --autogenerate -m "migration description"
```

Generated migrations should be reviewed before they are applied.

## Local Migration Testing

A temporary SQLite database can be used to verify migrations locally without modifying the Railway PostgreSQL database.

Apply the migrations:

```bash
DATABASE_URL="sqlite:///./alembic_test.db" python -m alembic upgrade head
```

Verify the current revision:

```bash
DATABASE_URL="sqlite:///./alembic_test.db" python -m alembic current
```

Roll back to the base schema:

```bash
DATABASE_URL="sqlite:///./alembic_test.db" python -m alembic downgrade base
```

Remove the temporary database after testing:

```bash
rm -f alembic_test.db
```

## Initial Migration

The initial migration creates:

```text
users
benchmark_runs
attempts
evaluations
```

The `users` table contains:

```text
id
email
password_hash
role
created_at
```

Allowed user roles are:

```text
viewer
member
admin
```

The `email` field is unique, and passwords are stored only as hashes.

The benchmark tables store model generations, repair attempts, token usage, compiler results, and evaluation results for ZakLang experiments.

## Railway PostgreSQL

The Railway development database should be kept at the latest Alembic migration.

To apply migrations to Railway, use the Railway-provided `DATABASE_URL` and run:

```bash
python -m alembic upgrade head
```

Then verify the database revision:

```bash
python -m alembic current
```

The reported migration should match the latest Alembic head.

Do not commit Railway database credentials, passwords, connection strings, or other secrets to Git.
