# ZakBench

ZakBench is the benchmark used to compare code generated in Zak against code
generated in Python for the same programming task.

The idea is that a model gets the same problem twice, once asked for Zak and
once asked for Python. We then run both solutions against the same hidden tests
and compare correctness and token usage.

This folder only holds benchmark material. It does not contain application or
web UI code.

## Layout

```text
zakbench/
├── tasks/        benchmark problem definitions + hidden tests
├── prompts/      Zak and Python prompt templates sent to the model
├── runners/      code that loads tasks, prompts the model, runs solutions
├── evaluation/   correctness checks, token accounting, timing, metrics
└── results/      output of benchmark runs
```

Each folder has its own README with more detail.

The backend records the prompt and Zak specification versions used for each
run. When prompt templates or the Zak language specification change, bump
`PROMPT_VERSION` in `runners/prompt.py` or `ZAK_SPEC_VERSION` in the backend
controller, and update the corresponding backend and ZakBench documentation.

## Storing a suite run in the database

`zakbench/results/` is not committed, so the deployed app cannot see suite
results that only exist there. Add `--persist` to also write the suite, every
run, and every attempt to the backend database:

```sh
DATABASE_URL=<postgres url> python3 -m zakbench run --suite dev --lang both     --model <id> --seed 0 --persist --user-email <your account email>
```

- `DATABASE_URL` is required with `--persist`. It is the same variable the
  backend reads. Keep it in your environment or in `backend/.env`. Never commit it.
- `--user-email` must belong to an existing account. The suite is recorded as
  launched by that user. An unknown email stops the command before any inference.
- `--persist` also needs `backend/requirements.txt` installed, and the database
  must have the latest migrations (`alembic upgrade head` in `backend/`).
- Each run is stored when it finishes. Both runs of a task share one `pair_id`.
  The suite status is `running` during the run, then `completed`, or `failed`
  if the suite stops early.
- The results folder, `summary.json`, and `runs.csv` are still written.

Without `--persist`, the runner does not connect to a database.

The API returns stored suites from `GET /suites` and `GET /suites/{id}`. The
second one includes the same summary as `summary.json`.
