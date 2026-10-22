# SD-39 Evaluator and Run Metrics Implementation Plan

**Goal:** One call scores a candidate in the sandbox and returns a bounded failure summary. One function computes run metrics.

**Spec:** `docs/superpowers/specs/2026-10-22-sd-39-evaluator-design.md`

**Stack:** Python 3.12+, stdlib, the existing `sandbox` and `compiler.src`. No new dependencies.

## Constraints

- Generated code runs only through `sandbox.runner.evaluate()`.
- Hidden tests leave the evaluator only inside the 500-char `failure_summary`. Nothing is logged or printed.
- The sandbox change is additive: one new field, no behavior change.
- Commits start with `SD-39`. No co-author trailers.

### Task 1: Run metrics

**Files:**
- Create `zakbench/__init__.py`, `zakbench/evaluation/__init__.py`, `zakbench/tests/__init__.py`.
- Create `zakbench/evaluation/metrics.py` and `zakbench/tests/test_metrics.py`.

- [x] Write the metrics tests (one pass, repaired pass, all fail, empty raises, repair identity).
- [x] Implement `Attempt`, `RunMetrics` and `compute_run_metrics()`.
- [x] Run `python -m unittest discover -s zakbench/tests -t .`; all pass.
- [x] Commit `SD-39: Compute per-run token and latency metrics`.

### Task 2: Keep the first failing value in the sandbox

**Files:** Modify `sandbox/runner.py` and `sandbox/tests/test_runner.py`.

- [x] Add a test: when case 2 of 5 returns a wrong value, `first_failure_actual` is that value as JSON. When it raised, the field is `None`.
- [x] `_execute` reads the first failing entry of the validated report and sets `SandboxResult.first_failure_actual`. `_score_report` is unchanged, so its existing tests keep passing.
- [x] Run `python -m unittest discover -s sandbox/tests -v`; all pass, old tests unchanged.
- [x] Commit `SD-39: Keep the first failing result in sandbox results`.

### Task 3: Evaluator

**Files:** Create `zakbench/evaluation/evaluator.py` and `zakbench/tests/test_evaluator.py`.

- [x] Write the evaluator tests from the spec:
  - Mock `sandbox.runner._execute` for the pass, fail, raised, timeout and crash cases.
  - Use the real compiler for the Zak compile error.
  - Add the no-output check and the 500-char bound.
- [x] Implement `EvalResult` and `evaluate()`: call the sandbox, build `per_test`, then build the summary for each outcome.
- [x] Run all tests: zakbench, sandbox, `pytest compiler/tests`.
- [x] Commit `SD-39: Add hidden-test evaluator with bounded failure summary`.

### Task 4: Docs and PR

**Files:** Modify `zakbench/evaluation/README.md`.

- [x] Document `evaluate()`, the summary format, `compute_run_metrics()`, the test command and the Docker requirement.
- [x] Commit `SD-39: Document the evaluator and run metrics`.
- [ ] Run the naming check, push, and open the PR. The PR body notes:
  - the reason for the interface change
  - the sandbox field addition (tell Horacio)
  - that the real Docker `array_sum` run is **pending until run with Docker**
- [ ] Move SD-39 to In Review once the Docker output is in the PR.

## Verification

- Unit tests pass: zakbench, sandbox, compiler.
- `docker build -t zaklang-sandbox ./sandbox`, then evaluating `array_sum/reference.py` and `array_sum/reference.zak`, gives `pass 6/6` for both (run by Zakaria; needs Docker Desktop).
