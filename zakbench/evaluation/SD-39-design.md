# SD-39: Hidden-test evaluator and run metrics

Status: design only. No implementation decisions have been approved. This
document records the supplied ticket requirements and a read-only inspection
of the local repository on October 8, 2026. Teammates may have additional work
on other branches. Implementation requires explicit approval to enter implement
mode.

## Ticket requirements

Evaluate Python source against a task's hidden tests through the SD-21 Docker
sandbox. Zak solutions use their transpiled Python, so both languages share
the evaluator and tests. Generated code must never execute in the calling
process. Sandbox implementation and aggregate benchmark metrics are out of
scope.

The proposed entry points are `evaluate(python_source, task, hidden_tests,
timeout_s=5.0)` and `compute_run_metrics(attempts)`. The evaluation result must
include `tests_passed`, `tests_total`, `per_test`, `exec_outcome`, and
`failure_summary`. Allowed execution outcomes are `pass`, `fail`, `timeout`,
`oom`, and `crash`.

Call the task's `functionName` with each test's `inputs` positionally and
compare the return value with `expected`. The failure summary contains only
the first failing test, including expected versus actual where available,
and is truncated. A 500-character limit is proposed in the ticket, but has
not been approved. Hidden tests must not be written to logs.

Run metrics are `passed`, `attempts_used`, `prompt_tokens_total`,
`completion_tokens_total`, `total_tokens`, `first_attempt_tokens`,
`repair_tokens`, and `latency_ms_total`. Repair tokens equal total tokens
minus first-attempt tokens.

## Existing task format

`../tasks/README.md` defines the required task fields: `id`, `title`,
`category`, `prompt`, `functionName`, `inputs`, and `outputType`.
Parameter definitions contain `name` and `type`; their order determines
positional argument order. The same task definition is used for both languages.

Each `hidden_tests.json` is a list of objects containing `inputs` and
`expected`. The outer inputs list represents function arguments; an array
parameter is therefore nested inside that list. The README specifies exact
comparison by value and avoiding fragile floating-point comparisons. It does
not explicitly define equality between values of different types.

Task descriptions and hidden tests are stored separately. Hidden-test values
must never enter model prompts. No hidden-test inputs or expected answers are
reproduced in this document.

| Existing task | Function name | Output type | Test count |
| --- | --- | --- | --- |
| array_sum | solve | integer | 6 |
| palindrome | solve | boolean | 6 |
| frequency_count | solve | map<string, integer> | 5 |

The existing array-sum task can support the ticket's correctness acceptance
criterion without introducing a new task format.

## Implementation gaps in this checkout

- Evaluation and runner folders contain documentation but no implementation.
- No `Attempt`, `EvalResult`, or `RunMetrics` types are defined.
- No SD-21 sandbox implementation or documented call interface was found.
- No Docker configuration was found. The backend GPU-health endpoint is not
  a solution-execution interface.
- The compiler test folder contains only an initialization file. No Python
  tests, pytest configuration, or Python test dependency were found.

## Questions requiring agreement

These are unresolved questions, not selected implementation behavior.

- With Horacio: what request and response does SD-21 support, and how does it
  distinguish timeouts, out-of-memory failures, and crashes?
- Do tests execute together or separately? Does the timeout apply per test or
  to the whole evaluation? Does execution continue after a failure?
- What fields belong in `per_test`, and how are unexecuted tests represented?
  Which overall outcome takes precedence when test outcomes differ?
- How should missing functions, invalid task data, and equal values of
  different types be handled?
- Is the proposed 500-character summary limit accepted? What should summaries
  contain when there is no return value, such as after a timeout or crash?
- Who may receive failure summaries? Expected-versus-actual details contain
  hidden-test information, so their use as repair feedback needs clarification.
  How will exceptions and captured output avoid leaking tests into logs?
- Who owns the shared attempt and result types? What determines run success,
  attempt ordering, and handling of empty attempts or missing token counts?
- Does latency include generation only or additional execution stages?
- What Python test framework and test layout should this work use?

## Verification required by the ticket

- Unit tests cover pass, fail, timeout, and crash outcomes.
- A correct array-sum solution passes every hidden test for that task.
- Failure summaries stay within the approved limit and describe at most one
  failing test.
- A unit test verifies `repair_tokens == total_tokens - first_attempt_tokens`.
- Hidden tests are not written to logs.

Tests using simulated sandbox responses can verify evaluator logic, but do
not establish actual execution isolation. Integration verification depends
on the SD-21 sandbox. Metrics work can proceed independently once its input
and output contracts are agreed.

## Next design step

Agree the sandbox call interface with Horacio before designing the execution
connection. Do not implement a replacement sandbox as part of this ticket.
