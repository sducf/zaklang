# SD-34: deterministic Zak-to-Python transpiler

## Outcome and branch

Implement `transpile(program: Program) -> str` for the checked SD1 subset.
The branch `SD-34-zak-python-transpiler` started at SD-32 commit `07f2679`.
PR #23 has since merged; the updated main branch has been merged into this
branch without rewriting published commits. The user will review SD-34
directly on this branch and explicitly requested that no PR be opened.

SD-35 remains blocked: it still needs this transpiler and isolated execution
support. SD-21 is In Progress and SD-39 is To Do in Jira. Neither execution
component exists in this checkout. SD-34 is the next actionable compiler
ticket because its AST dependency is available on the parent branch.

## Approach and alternatives

Recommend a separate emitter over the existing immutable Zak AST. Construct
Python standard-library AST nodes and render them consistently with
`ast.unparse`, followed by a final newline. This handles Python precedence,
literal escaping, and statement structure without a custom code formatter.
Determinism is measured on the same supported Python runtime.

A direct text emitter would give tighter formatting control but require
maintaining escaping and precedence. Translating Lark trees directly would
couple the transpiler to parsing internals and bypass SD-32's interface.

## Interfaces and files

- `compiler/src/analysis.py` (or a small public analysis interface in
  `semantic.py`): expose semantic diagnostics plus expression types keyed
  by node identity for this compilation. Preserve existing `check(program)`
  and `compile(source)` behavior and immutable AST shape. Reuse the checker
  rather than duplicate its type inference in the emitter.
- `compiler/src/transpiler.py`: `transpile(program: Program) -> str` validates
  its input, emits standalone Python, and raises a documented
  `TranspileError` containing structured diagnostics for invalid or
  unsupported ASTs. It never executes either language.
- `compiler/src/__init__.py`: export `transpile` and `TranspileError`.
- `compiler/tests/test_transpiler.py` and checked-in output snapshots:
  emission, semantic preservation, and deterministic output tests.
- `compiler/README.md`: usage, output conventions, and handoff for SD-35.

The existing static diagnostics CLI keeps its behavior. Python emission
does not automatically run as part of `compile(source)`.

## Semantics to preserve

Translate declarations, assignment/update, append, return, break/continue,
functions, conditions, while loops, ranges, and collection iteration.
Expressions cover every construct currently accepted by SD-32, including
primitive casts, conditional expressions, strings, arrays, and maps.
Unsupported comprehensions must fail explicitly.

Use semantic types to emit `//` and `//=` for integer division, `/` and `/=`
for R. Preserve negative floor semantics, short-circuit boolean operators,
half-open ranges, missing slice bounds, and single evaluation of targets in
augmented assignments. Map key/value loops use `.items()`.

Preserve SD-32's lexical scopes by assigning deterministic generated Python
identifiers to variable bindings. This also permits Zak names that happen to
be Python keywords and prevents collisions with builtins or emitter names.
Branch declarations and loop variables must not overwrite enclosing names;
assignments still update their resolved enclosing binding. Emit `global`
declarations when a function rebinds a module binding.

Resolve function names in advance for recursion and forward calls. Hoist
function definitions ahead of top-level executable statements while
resolving their global bindings according to the existing checker rules.
Export user functions under their original names through module aliases so
the task evaluator can find `solve`; internal call targets stay collision
free. Do not promise to prove global initialization order at runtime.

Map the documented SD-32 builtins to qualified Python builtins or standard
container/string operations. Import Python `builtins` under a reserved
generated alias; all user bindings are separately generated. `srt` and `rev`
return copies; `keys` and `vals` return arrays; R-array `sum` uses a float
initial value so empty arrays preserve their type. `out` follows Python
`print` formatting and trailing-newline behavior. Primitive casts use the
corresponding Python conversion; runtime conversion failure remains possible.

Output runs standalone on CPython 3.12+ without third-party runtime helpers.

## Validation and commit tasks

1. Add reusable semantic type analysis with regression tests proving the
   existing diagnostics remain unchanged.
2. Implement the emitter with exact snapshots, repeat-emission checks, and
   focused tests for integer/float division, lexical shadowing, global
   assignments, keyword names, recursion, side-effecting targets, and each
   supported builtin. Cover unsupported AST rejection.
3. Compile/transpile all 15 conformance fixtures and three references;
   require all emitted Python to pass Python syntax compilation. Document
   the interface and the remaining execution handoff.

Commit each task separately, preserving the user's local `.gitignore` edit.
Run the full compiler suite before claiming completion. Development checks
of trusted hand-written examples can use fresh, time-limited Python
subprocesses; they must not be described as the project's sandbox.
Do not execute generated code in the test runner or API process.

SD-34's hidden-test acceptance requires validating all three trusted,
hand-written task references against their existing JSON cases in fresh,
time-limited development subprocesses. This does not implement the production
sandbox or evaluator; SD-35's production execution integration remains
pending. Never silently skip reference validation or claim SD-35 complete.
