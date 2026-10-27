# Zakc executable conformance fixtures

The 15 hand-written programs and their `.expected` files describe exact stdout,
including final newlines. They parse through `zakc/src/zak.pest` into the native
Rust AST; integer division uses floor semantics. Programs avoid dependence on
map iteration order and float rounding.

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


## Run every conformance check

Use the full setup in [zakc/README.md](../../README.md#run-all-tests), from the
repository root, including building the optional Python extension and Docker
image. Then run:

```sh
# Native fixture structure, parsing, AST construct coverage, reference signatures.
cargo test --manifest-path zakc/Cargo.toml --test fixtures

# Exact stdout and reference grading in the real Docker sandbox.
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests/conformance -q
```

`test_conformance.py` uses the native `zakc.zak_transpile` binding and checks
emitted Python against Python 3.12 grammar compatibility. It executes each
of the 15 fixture programs through `sandbox.runner.execute_program` and
compares stdout bytes exactly. The three sample references (`array_sum`,
`palindrome`, and `frequency_count`) run through the existing evaluator in
Python mode, so it grades Rust-generated Python directly. A separate contract
ensures direct candidate stdout cannot corrupt the final grading report.

Each execution uses the existing disposable Docker sandbox with no network,
a read-only filesystem, a non-root user, resource limits, and a timeout.
Expected stdout and hidden expected answers remain on the host. Missing Docker,
image, native module, or fixtures fails the suite; there are no automatic skips.

`zakc/tests/fixtures.rs` replaces the old Lark fixture checks with real Rust
AST checks: fixture pairing, trailing newlines, all 30 required construct
families, and function/parameter signatures matching every task's metadata.
`zakc/tests/test_transpiler_corpus.py` separately syntax-checks all emitted
programs and runs all fixtures and discovered references in time-limited
trusted development subprocesses. Those local checks need no Docker:

```sh
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests/test_transpiler_corpus.py -q
```

Static checking of all fixtures and references is available through the CLI:

```sh
cargo run --manifest-path zakc/Cargo.toml -- --emit check zakc/tests/conformance zakbench/tasks
```
