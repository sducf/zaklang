# SD-34 Transpiler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Emit deterministic standalone Python for every SD1 program accepted by SD-32.

**Architecture:** Retain SD-32's immutable AST and expose expression-type analysis. A separate emitter builds Python AST nodes, preserving lexical bindings and typed division, then renders source with stdlib `ast.unparse`.

**Tech Stack:** Python 3.12+, stdlib ast, existing Lark and pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-sd-34-transpiler-design.md`

## Global Constraints

- `transpile(program: Program) -> str` never executes source.
- Standalone CPython 3.12+ output; no third-party runtime helpers.
- Strict SD-32 types, lexical scopes, and integer floor division are preserved.
- Invalid/unsupported programs raise structured `TranspileError`.
- Preserve PR #23's parent branch and the user's `.gitignore` edit.
- Work on SD-34 before moving to SD-35.

## Review Focus

- Nested bindings and Python keyword names must not collide (Task 2).
- Indexed augmented assignments must evaluate targets once (Task 2).
- Function rebinding of globals must use the resolved global binding (Task 2).
- Typed empty arrays must retain correct division/sum semantics (Tasks 1–2).
- Generated code and hidden-test inputs must stay out of the parent process (Task 3).

### Task 1: Reusable expression-type analysis

**Files:** Modify `compiler/src/semantic.py`; create `compiler/tests/test_analysis.py`.

**Interfaces:** `analyze(program: Program) -> AnalysisResult` with `errors: list[CompileError]` and `expression_types: dict[int, Type]`, keyed by `id(node)` for the input AST's lifetime. Preserve `check(program) -> list[CompileError]` as a wrapper. Include assignment-target types and void statement calls.

- [x] Write tests for I/R division expression types, contextual nested empty arrays, target types, void calls, matching diagnostics, and independent analyses without stale results.
- [x] Run `python -m pytest compiler/tests/test_analysis.py -q`; expect missing analysis interface failure.
- [x] Add `AnalysisResult`, record types during the existing checker traversal, and return analysis metadata without changing ASTs or diagnostics.
- [x] Run `python -m pytest -q`; require all old and new tests to pass.
- [x] Commit as `SD-34 Expose semantic expression types for transpilation`.

### Task 2: Standalone Python emitter

**Files:** Create `compiler/src/transpiler.py`, `compiler/src/python_emitter.py`, `compiler/tests/test_transpiler.py`, `compiler/tests/snapshots/*.py.txt`; modify `compiler/src/__init__.py`.

**Interfaces:** Public `transpile(program: Program) -> str`; `TranspileError.errors: list[CompileError]`. Consume Task 1 metadata, reject diagnostic-bearing ASTs, and return source with final newline. A private emitter owns name scopes and Python AST construction.

- [x] Write exact snapshot and repeat-emission tests for functions, branches, loops, typed division, containers, and builtins; syntax-compile every emitted module. Add invalid AST rejection tests.
- [x] Write child-process tests with literal stdout expectations for negative floor division, float division, casts, short circuiting, shadowed bindings, global assignment, keyword names, recursion/forward calls, augmented target evaluation, and every builtin.
- [x] Run the new tests and confirm the emitter interface is missing.
- [x] Implement deterministic binding identifiers, function hoisting and exports, qualified builtin lowering, and Python AST emission. Use typed floor division and float start values for `sum([R])`.
- [x] Run the full suite; require unchanged static diagnostics and passing emitter tests.
- [x] Commit as `SD-34 Emit deterministic Python for the checked Zak subset`.

### Task 3: Corpus/reference validation and documentation

**Files:** Create `compiler/tests/test_transpiler_corpus.py`; modify `compiler/README.md` and `compiler/tests/conformance/README.md`.

**Interfaces:** Compile all 18 trusted hand-written Zak files through the public API; syntax-check emitted Python. Run trusted references in fresh `python -I` child processes with timeouts and compare results against JSON cases. This is development verification, not the SD-21 production sandbox.

- [x] Write parameterized syntax tests for all 18 outputs and child-process checks for the three references' 17 hidden cases. Use explicit timeout/error failures, never skip absent dependencies.
- [x] Run targeted checks and the full suite, and record actual results. Any compiler/emitter failure gets a reproducing regression before its fix.
- [x] Document the public transpiler API and builtin/scope behavior. Keep SD-35's production-sandbox conformance runner pending; do not claim that separate ticket complete.
- [x] Commit as `SD-34 Validate transpiled fixtures and task references`.

## Execution and review

User authorized beginning SD-34 on the stacked branch. Execute natively, using TDD and separate task commits. Obtain one read-only independent review using the requesting-code-review skill, fix Important findings with regression tests, then push the SD-34 branch. Do not merge the feature into main or change Jira assignments. The user subsequently requested direct branch review and no SD-34 PR.

## Scope ruling

SD-34 lists SD-32 as its dependency, whereas SD-35 requires the project's
isolated execution runner. Trusted hand-written reference validation in
separate development subprocesses is sufficient to verify SD-34's emitter;
it does not implement or replace SD-21/SD-39. The design's earlier statement
that SD-34 must wait for that service is narrowed accordingly. Production
execution remains pending, and SD-35 will be addressed separately.


## Execution record

Completed task commits: `bce2eb0` (analysis metadata), `25064a7` (emitter),
`7154ebf` (corpus/reference validation and docs). A read-only independent
review found no Important or Critical defects and independently confirmed
234 passing tests. Validation ran on Python 3.14.4; every emitted corpus
module also passed the Python 3.12 syntax feature check. A separate CPython
3.12 runtime was not available for execution testing.

All 18 outputs pass `py_compile`, all 15 trusted fixture outputs match their
expected bytes, and all three references pass their 17 JSON cases in child
processes. No generated code executes in the test parent process.

Review rulings: array augmented assignment uses Python's in-place update
semantics (alias behavior was not specified otherwise); runtime global
initialization ordering and adversarial execution remain outside this
transpiler's static guarantees; hand-forged AST nodes with invented operators
or primitive types are outside the supported parser-owned AST contract.
These limitations do not prevent emission of the statically accepted SD1
subset, and production sandbox integration remains SD-35 work.

After the user reported PR #23 merged and its branch deleted, fetched main
and merged `2259053` into SD-34 without rewriting the published task commits.
Temporarily preserved and then restored the user's local `ZakContext/`
ignore entry while incorporating main's `.gitignore` update. No SD-34 PR was
created; the branch is reserved for the user's review.
