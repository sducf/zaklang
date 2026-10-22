# SD-39: hidden-test evaluator and run metrics

## Outcome and branch

Give SD-36's runner one call that scores a candidate (Python or Zak) against
a task's hidden tests in the Docker sandbox. The call returns a short
failure summary to feed back to the model. A second function turns a run's
attempts into the PRD F5 run metrics. Branch
`SD-39-hidden-test-evaluator-and-run-metrics` from `main` at `7fc6c5d`.

## Current state

- SD-21's sandbox is merged. `sandbox/runner.py:311`
  `evaluate(source, task_id, language, *, tasks_root, image, timeout_s)
  -> SandboxResult` already does the following:
  - validates the task id
  - compiles and transpiles Zak on the trusted side
  - syntax-checks Python
  - runs all tests in one hardened container with one timeout
  - compares results with the expected answers on the host
  - returns `pass | fail | timeout | oom | crash | not_run`
- What it does not give SD-36:
  - **No failure summary.** It returns only failing case numbers. The
    candidate's actual return values are dropped in `_score_report`.
  - **No run metrics.** Nothing computes them anywhere.
- Josh's design notes (branch `sd-39-evaluator-design`) list open questions.
  The merged sandbox answers most of them:

| Question | Answer |
|---|---|
| Sandbox request/response | `sandbox.runner.evaluate()` → `SandboxResult` |
| Timeout vs OOM vs crash | `docker wait` timeout → `timeout`; `State.OOMKilled` → `oom`; non-zero exit or bad report → `crash` |
| Tests together or separately; timeout scope | Together in one container; timeout covers the whole file; every test runs |
| Missing function | Grader fails at import → `crash` |
| Different types that compare equal | Python `==` on JSON values, as the sandbox does (`1 == 1.0` passes); task authors avoid floats |
| Summary limit | 500 chars (ticket default) |
| Who sees the summary | The model, in the repair prompt (PRD F5 step 4). Never logged, never sent to the browser |

## Interface (deviation from ticket, on purpose)

The ticket proposes `evaluate(python_source, task, hidden_tests, timeout_s)`.
The sandbox instead takes `task_id` and loads trusted fixtures from disk
itself, with path-traversal checks. It also already handles Zak. Passing
hidden tests as objects would mean writing them back to disk. So the
evaluator follows the sandbox:

```python
# zakbench/evaluation/evaluator.py
SUMMARY_LIMIT = 500

@dataclass
class EvalResult:
    exec_outcome: str              # pass | fail | timeout | oom | crash | not_run
    tests_passed: int
    tests_total: int
    per_test: list[bool]           # empty unless the tests actually ran (pass/fail)
    failure_summary: str | None    # None on pass
    compile_ok: bool | None
    compile_errors: list[dict]
    transpiled_python: str | None
    execution_ms: float

def evaluate(source: str, task_id: str, language: str = "python", *,
             timeout_s: float = 5.0, tasks_root: Path = DEFAULT_TASKS) -> EvalResult: ...
```

```python
# zakbench/evaluation/metrics.py
@dataclass(frozen=True)
class Attempt:
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    passed: bool

@dataclass(frozen=True)
class RunMetrics:
    passed: bool
    attempts_used: int
    prompt_tokens_total: int
    completion_tokens_total: int
    total_tokens: int
    first_attempt_tokens: int
    repair_tokens: int
    latency_ms_total: int

def compute_run_metrics(attempts: list[Attempt]) -> RunMetrics: ...
```

`Attempt` holds only what the metrics need. SD-36 can build it from its own
attempt record and doesn't have to inherit fields it doesn't use.

## Behavior

**Sandbox change (small, additive).**
- After scoring, `_execute` takes the candidate's value for the first failing
  test as compact JSON, or `None` if that call raised. `_score_report` is
  unchanged.
- `SandboxResult` gets one new field, `first_failure_actual: str | None`.
- Expected answers stay host-side. The CLI output gains only the candidate's
  own value, never a hidden one.
- One sandbox unit test is added.

**`evaluate()`:**
1. Call `sandbox.runner.evaluate(...)`. Its `ValueError` (bad input) and
   `RuntimeError` (Docker missing or failed) propagate unchanged. The runner
   marks the run `error`.
2. `per_test`:
   - On `pass`/`fail`: `[i not in failed_tests for i in 1..total]`.
   - Otherwise: empty.
3. `failure_summary`, truncated to `SUMMARY_LIMIT` with a trailing `...`:
   - `pass`: `None`.
   - `fail`: read `hidden_tests.json` (the sandbox has already validated the
     task id) and describe only the first failing case:
     `Test 3 of 7 failed. Inputs: [..]. Expected: ... Got: ...`. When the call
     raised: `Got: an exception`.
   - `not_run`, with compile errors:
     `Compile error at 1:5: E_SYNTAX: ...`, one line per error.
   - `not_run`, without compile errors: the sandbox `detail`
     (`Zak transpilation failed`).
   - `timeout` / `oom` / `crash`: a fixed sentence per outcome, for example
     `Execution timed out after 5s.`
4. Never logs or prints. The only hidden data that leaves is the bounded
   summary.

**`compute_run_metrics()`:**
- Empty list raises `ValueError`.
- `passed` = the last attempt passed.
- `first_attempt_tokens` = attempt 1's prompt + completion tokens.
- `repair_tokens = total_tokens - first_attempt_tokens`.

## Tests (unittest, Docker mocked like `sandbox/tests/test_runner.py`)

`zakbench/tests/test_evaluator.py`, using a temporary task folder and
patching `sandbox.runner._execute` or `sandbox.runner.evaluate`:

- `pass`: no summary; `per_test` all True.
- `fail`:
  - the summary names only the first failing test, with its inputs, expected
    and actual values
  - `per_test` matches `failed_tests`
  - a huge actual value stays within 500 chars
- `fail` where the call raised: `Got: an exception`.
- `timeout` and `crash`: fixed summaries, `per_test` empty.
- Zak `not_run`: a real compile error from `compiler.src` is formatted
  (no Docker involved).
- Nothing is written to stdout or stderr during evaluation
  (`contextlib.redirect_stdout` check).

`zakbench/tests/test_metrics.py`:
- One passing attempt.
- Three attempts where the last one passes.
- All failing.
- Empty list raises.
- `repair_tokens == total_tokens - first_attempt_tokens`.

Real sandbox AC: with Docker running, `array_sum/reference.py` evaluates to
`pass 6/6`. Done by hand (`docker build -t zaklang-sandbox ./sandbox`, then a
one-liner) and pasted in the PR.

## Files

- Modify `sandbox/runner.py` (new field and return value) and
  `sandbox/tests/test_runner.py` (one test).
- Create `zakbench/__init__.py`, `zakbench/evaluation/__init__.py`,
  `zakbench/tests/__init__.py` (empty; identical to SD-38's).
- Create `zakbench/evaluation/evaluator.py` and `zakbench/evaluation/metrics.py`.
- Create `zakbench/tests/test_evaluator.py` and `zakbench/tests/test_metrics.py`.
- Update `zakbench/evaluation/README.md`.

## Out of scope

Aggregate metrics (SD-44), persistence (SD-31), repair prompt wording (SD-36),
replacing or reworking the sandbox.
