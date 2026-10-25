# evaluation/

Code that scores a benchmark run (SD-39). Run everything from the repository
root.

## evaluator.py

`evaluate()` runs a Python or Zak candidate against a task's hidden tests in
the SD-21 Docker sandbox (`sandbox/runner.py`). Zak is compiled and
transpiled first, so both languages run the same tests the same way.
Generated code never runs in the calling process.

```python
from zakbench.evaluation.evaluator import evaluate

result = evaluate(source, 'array_sum', 'zak')
result.exec_outcome      # pass, fail, timeout, oom, crash, or not_run
result.tests_passed, result.tests_total, result.per_test
result.failure_summary   # repair feedback for the model; None on pass
```

`failure_summary` is at most 500 characters and describes one problem:

| Outcome | Summary |
|---|---|
| `fail` | `Test 2 of 5 failed. Inputs: [...]. Expected: 4. Got: 5.` Only the first failing test. `Got: an exception.` when the call raised. |
| `not_run` | `Compile error at 1:5: CODE: message`, one line per error |
| `timeout`, `oom`, `crash` | A fixed sentence, for example `Execution timed out after 5s.` |

The summary is the only hidden-test data that leaves the evaluator. Send it
to the model, never to logs or the browser.

The task id is how `evaluate()` finds the task. It does not take hidden tests
as arguments: the sandbox loads them from `zakbench/tasks/<id>/` itself, after
checking the id. Invalid input raises `ValueError`. A missing or failing
Docker raises `RuntimeError`. Running it for real needs the sandbox image:

```sh
docker build -t zaklang-sandbox ./sandbox
```

## metrics.py

`compute_run_metrics(attempts)` turns a run's attempts, in order, into the PRD
F5 run metrics: `passed`, `attempts_used`, `prompt_tokens_total`,
`completion_tokens_total`, `total_tokens`, `first_attempt_tokens`,
`repair_tokens`, and `latency_ms_total`. A run passes if its last attempt
passed, and `repair_tokens = total_tokens - first_attempt_tokens`.

## summary.py

`summarize(runs)` turns the stored run records of one suite run into the PRD F5
aggregate metrics (SD-44). It is a pure function: it reads only the run
records, so `zakbench summarize` can recompute a summary without inference.
The runs must form one Zak run and one Python run per task under one run
definition. Otherwise it raises `ValueError`.

The summary has an `overall` block, the same block for each task `category`
in `by_category`, and a list of `errors`. Each block holds:

| Metric | Meaning |
|---|---|
| `pass_at_1` | Share of tasks whose first attempt passed, per language |
| `pass_at_k` | Share of tasks that passed within `max_attempts` (K), per language |
| `correctness_gap` | Zak `pass_at_k` minus Python `pass_at_k` |
| `repair_token_share` | `repair_tokens` divided by `total_tokens`, over all runs of a language |
| `paired.tasks` | Tasks that both languages solved |
| `paired.<language>` | Mean and median `total_tokens` over the paired tasks only |
| `paired.token_ratio` | Zak tokens divided by Python tokens, summed over the paired tasks |
| `paired.token_ratio_by_task` | Zak tokens divided by Python tokens, for each paired task |
| `solved_by_zak_only`, `solved_by_python_only`, `solved_by_neither` | Tasks left out of the paired token stats |

An error run (a run that crashed the harness) counts as not passed. Rates and
ratios have 4 decimal places. A ratio is `null` when there is nothing to
divide by, for example when no task is paired.

## Tests

Docker is faked, so no image is needed. The Zak tests need
`compiler/requirements.txt` installed.

```sh
python3 -m unittest discover -s zakbench/tests -t .
```
