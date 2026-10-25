# SD-35 conformance execution implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. Steps use checkboxes for tracking.

**Goal:** Make `pytest compiler/tests/conformance` prove all 15 exact stdout fixtures and the three sample Zak references work through Docker isolation.

**Architecture:** Add standalone Python execution to the existing sandbox runner, sharing container restrictions, timeout handling, and cleanup with task evaluation. Conformance tests compile and transpile Zak, syntax-check emitted Python, execute programs through the sandbox, and run the three references through SD-39's evaluator.

**Tech stack:** Python 3.12+, pytest, existing compiler, SD-21 Docker sandbox, SD-39 evaluator.

**Spec:** [SD-35](https://notgui.atlassian.net/browse/SD-35), including its execution handoff comment; `compiler/tests/conformance/README.md`.

## Global constraints

- Branch and every new commit start with `SD-35-`.
- Compare stdout bytes exactly, including whitespace, line endings, and the final newline.
- Candidate code executes only inside Docker; syntax compilation on the host never executes it.
- Preserve all existing container restrictions and host-side hidden-answer comparison.
- Missing Docker, image, compiler, transpiler, or fixture files fail checks; no silent skips or fallback execution.
- Scope is 15 existing fixtures and `array_sum`, `palindrome`, `frequency_count`; CI and negative compiler tests remain outside this ticket.

## Approach

Reuse the existing sandbox and share its container lifecycle. A separate Docker runner would duplicate isolation and cleanup policy. Wrapping stdout fixtures as artificial benchmark functions would alter module execution and introduce fake test metadata. Native standalone execution preserves the program behavior and leaves task evaluation intact.

## Review focus

- Preserve raw stdout bytes, including CRLF, Unicode, blank output, and trailing spaces; keep stderr separate.
- A nonzero exit, timeout, OOM, or oversized output must never count as a passing program.
- Every exit path removes the container, including Docker failures.
- Expected stdout and hidden expected answers never enter the container.
- Explicit corpus membership prevents deleted fixtures or references from reducing coverage unnoticed.

## Task 1: Standalone sandbox execution

**Files:** `sandbox/runner.py`, `sandbox/tests/test_runner.py`, new `sandbox/tests/test_program.py`, `sandbox/README.md`.

**Interfaces:** `execute_program(source: str, *, image: str = IMAGE, timeout_s: float = 5.0) -> ProgramResult`; result contains outcome, raw stdout/stderr bytes, exit code, elapsed milliseconds, and optional detail. Shared private container execution also serves existing `evaluate()`.

- [x] Write failing unit tests for byte preservation, isolated mounts and flags, invalid input and syntax, runtime failure, timeout/OOM/output limits, missing Docker, and cleanup after failures.
- [x] Run the tests and observe the missing interface failure.
- [x] Implement the shared container lifecycle and standalone Python execution; retain the existing task evaluator behavior.
- [x] Run sandbox and evaluator unit tests, then real Docker checks for stdout, crash, timeout, and cleanup.
- [x] Commit as `SD-35-Add standalone program execution to the Docker sandbox`.

## Task 2: Executable conformance suite

**Files:** new `compiler/tests/conformance/test_conformance.py`; update `compiler/tests/conformance/test_fixtures.py`, its README, and `compiler/README.md`.

**Interfaces:** 15 explicit parameterized stdout checks and three explicit parameterized reference checks. Syntax-check all emitted Python with Python 3.12 grammar compatibility and builtin `compile`; call `execute_program` for stdout and `zakbench.evaluation.evaluate` for hidden-test references.

- [ ] Add the conformance tests and require the exact 15 fixture names and three sample reference files.
- [ ] Verify the tests detect an incorrect expected stdout and a wrong reference result, then restore fixtures.
- [ ] Strengthen construct coverage assertions for the constructs in the fixture coverage table.
- [ ] Update documentation with Docker setup, test commands, guarantees, and the separation from trusted development subprocess checks.
- [ ] Run conformance, all relevant unit suites, full Docker smoke, and naming validation; record results below.
- [ ] Commit as `SD-35-Run conformance fixtures and references through isolation`.

## Execution record

Baseline: updated main `ceb4b59`; branch `SD-35-sandbox-conformance`; 308 tests pass. Built the existing sandbox image and all 24 smoke checks passed before changes. Work proceeds in the user's requested checkout.

Task 1: 28 new sandbox tests pass (including the combined output limit regression); 48 sandbox/evaluator checks pass in total. All 24 existing Docker smoke checks pass. Real standalone checks preserve raw bytes and stderr, handle empty output, crashes, timeouts and output limits, fail for a missing image, and leave no containers behind.
