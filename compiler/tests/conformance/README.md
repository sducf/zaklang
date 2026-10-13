# SD-35 conformance fixtures

This is the fixture increment of SD-35. The 15 hand-written programs and
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

## Run the current checks

From the repository root, using Python 3.12 or newer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r compiler/requirements-dev.txt
.venv/bin/python -m pytest compiler/tests
```

`test_fixtures.py` loads the real grammar with Lark's LALR parser, parses every
program and reference, checks fixture pairing, checks SD1 syntax coverage,
and verifies reference function/parameter names against task metadata.
These are grammar checks, not semantic or execution checks. Expected stdout
has not yet been verified by the Zak compiler.

## Remaining work after SD-32 and SD-34

The checkout currently has no `compile(source)` implementation, AST interface,
or `transpile(program)` implementation. Once those dependencies land:

1. Add `test_conformance.py` to compile every program, assert compilation
   succeeds, and transpile its AST.
2. Syntax-check the emitted Python, then execute it through the project's
   isolated execution service and compare stdout bytes with `.expected`.
3. Compile and transpile each sample task's `reference.zak`, then run its
   `solve` function against `hidden_tests.json` through the same isolation.
4. Require all execution checks to pass before closing SD-35. Missing compiler,
   transpiler, or sandbox support must fail the execution checks rather than
   silently skip them.

No generated program is executed by the current grammar checks.
