# SD-35 executable conformance suite

The 15 hand-written programs and
their `.expected` files describe exact stdout, including the final newline.
They follow `compiler/src/grammar.txt`; integer division uses floor semantics.
Programs avoid dependence on map iteration order and float rounding.

| Program | Coverage |
| --- | --- |
| 001_variables | Inferred and typed declarations, reassignment |
| 002_integer_arithmetic | Precedence, parentheses, floor division, negatives, modulo |
| 003_float_arithmetic | Explicit float declarations, addition and division |
| 004_boolean_logic | Boolean literals, and, or, not |
| 005_conditionals | If, elif, else, comparison |
| 006_nested_conditionals | Nested branches |
| 007_while_loop | While, counter updates |
| 008_range_loop | Half-open integer range |
| 009_array_iteration | For each array element |
| 010_functions | Typed parameters, return, call |
| 011_recursion | Recursive calls, early return |
| 012_arrays | Typed empty array, append, index assignment, length |
| 013_strings | Length, indexing, slicing, comparison |
| 014_maps | Typed empty map, membership, entry updates, key/value iteration |
| 015_break_continue | Break and continue inside a range loop |

The three sample task folders also contain `reference.zak` implementations
with the function and parameter names required by their `task.json` files.
Reference solutions are development artifacts, never prompt inputs.

## Run the suite

From the repository root, using Python 3.12 or newer and a running Docker
daemon (enable WSL integration in Docker Desktop when using WSL):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r compiler/requirements-dev.txt
docker build -t zaklang-sandbox ./sandbox
.venv/bin/python -m pytest compiler/tests/conformance -q
```

`test_conformance.py` checks each of the 15 programs through the public
`compiler.src.compile` and `transpile` APIs, syntax-checks emitted Python
(including Python 3.12 grammar compatibility), then executes it with
`sandbox.runner.execute_program`. It compares stdout bytes exactly with
`.expected`: spaces, blank lines, line endings, and final newlines matter.
Stderr is separate, and a nonzero exit cannot pass even if stdout matches.

The same test module compiles and transpiles `array_sum`, `palindrome`, and
`frequency_count` references, then passes their emitted Python through
SD-39's evaluator and SD-21's Docker sandbox. All 17 hidden cases must pass.
Failures identify the task and outcome without printing hidden case values.

Each execution uses a disposable container with no network, a read-only
filesystem, non-root user, dropped capabilities, resource limits, and a
five-second timeout. Only the required files enter Docker. Expected stdout
and hidden expected answers stay on the host. Containers are removed after
successful runs and failures. Standalone output is limited to 65,536 bytes
across stdout and stderr; oversized output fails.

Missing compiler/transpiler support, Docker, the sandbox image, or fixture
files fails the suite. There are no automatic skips or local execution
fallbacks. Running all compiler tests now includes these Docker checks:

```sh
.venv/bin/python -m pytest compiler/tests -q
```

## Other checks

`test_fixtures.py` loads the real grammar with Lark's LALR parser, parses every
program and reference, checks fixture pairing, checks SD1 syntax coverage,
and verifies reference function/parameter names against task metadata.
These are grammar checks. SD-32's `test_semantic.py` and `test_compile.py`
add static checks for all 15 programs and all three references. SD-34's
`test_transpiler_corpus.py` additionally syntax-checks all emitted Python,
compares all 15 stdout files, and checks the available task references using
fresh, time-limited development subprocesses. Those trusted-example checks
are separate from this suite's Docker execution.
To check the files statically:

```sh
.venv/bin/python -m compiler.src compiler/tests/conformance zakbench/tasks
```

The grammar checks never execute generated code. Their construct assertions
cover the supported SD1 families in the table above; comprehensions remain
outside the compiler's supported subset. Expansion to 40 programs and CI
wiring belong to later tickets.
