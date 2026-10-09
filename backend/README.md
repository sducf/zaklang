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