# ZakLang Docker Sandbox — SD-21

Local prototype for executing generated Python and transpiled Zak
code against ZakBench hidden tests.

## Architecture

1. The trusted runner loads the task and hidden tests.
2. For Zak submissions, the compiler transpiles Zak to Python.
3. The runner creates a temporary file with test inputs only.
4. Docker executes the candidate and returns its actual outputs.
5. The trusted runner compares outputs with expected answers.
6. The runner returns a bounded pass/fail summary and removes
   the temporary container.

Expected answers are never mounted inside Docker.

## Security

Each container runs with:
- No network access
- Read-only root filesystem
- Non-root user
- All Linux capabilities dropped
- No privilege escalation
- 256 MB memory limit
- One CPU
- 64-process limit
- Restricted temporary storage
- Five-second default execution timeout

The sandbox does not receive database credentials, user
passwords, JWT tokens, or the complete repository.

This is a development prototype, not a production-grade
security boundary for arbitrary hostile code.

## Build

From the repository root:

    docker build -t zaklang-sandbox ./sandbox

## Unit tests

    python -m unittest discover -s sandbox/tests -v

## Docker smoke tests

    python -m sandbox.smoke
    python -m sandbox.smoke --full

## Run one task

    python -m sandbox.runner --task array_sum --language python --file zakbench/tasks/array_sum/reference.py

## Backend integration

A future authenticated benchmark worker can call
sandbox.runner.evaluate() and persist the results into the
existing benchmark_runs, attempts, and evaluations tables.

Authentication, quota enforcement, queues, and database
persistence are outside the scope of this prototype.