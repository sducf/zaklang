# Zakc executable conformance fixtures

The 40 hand-written programs and their `.expected` files describe exact stdout,
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
| 016_string_building | String concatenation in a range loop, `S()` cast, string iteration, prepend |
| 017_string_slicing | Prefix, suffix, and middle slices; length of a slice; last-index access |
| 018_string_case_compare | `up`, `lo`, string ordering comparison, multi-part concatenation |
| 019_split_join | `spl` with an empty field, `jn`, `rev` on a string array |
| 020_map_get_set_has | Map literal, insert, compound update, membership miss/hit, map length |
| 021_map_sorted_keys | `keys` + `srt` for deterministic order, lookup by sorted key |
| 022_map_delete | Integer-keyed map, `del`, membership after delete |
| 023_map_of_arrays | `{S:[I]}` values, append through a map entry, `sum` per entry |
| 024_array_of_arrays | Nested literal, double indexing, diagonal loop, nested index assignment |
| 025_nested_build_grid | Nested loops building `[[I]]` (transpose), row-to-string building |
| 026_nested_break | Break out of an inner loop, flag-driven break of the outer loop |
| 027_nested_continue | Continue in both the outer and inner loop |
| 028_nested_early_return | Return from inside nested range loops, computed range bounds, not-found result |
| 029_recursion_over_array | Index-driven recursion: sum and maximum, ternary on the result |
| 030_recursion_strings | Recursive string reversal with slices, boolean-returning helper |
| 031_mutual_recursion | Two functions calling each other, boolean results in conditions |
| 032_helper_functions | Three functions composing, explicit `R()` casts, float result |
| 033_filter_map_loops | Filter and map with loops and appends, `jn` of converted values |
| 034_sort_reverse_minmax | `srt` copy semantics, `rev`, `min`, `max`, `abs` |
| 035_stack_pop | Append in a loop, `pop` in a length-driven while loop |
| 036_while_collatz | Data-dependent while loop with an if/else body, `/=` update |
| 037_negative_floor_mod | Floor division and modulo with negative operands, `/=`, `*=`, `%=` |
| 038_float_casts | Float arithmetic, `R()`/`I()` truncation, string-to-int cast |
| 039_elif_chain_ternary | Elif chain with a return in every branch, ternary expression |
| 040_word_frequency | Split, lowercase, counting map, sorted keys, `S()` in output (dev-task shape) |

Programs 016–040 (SD-56) cover the construct combinations the 50 dev-task
references use. Their expected output was computed by hand and then confirmed
against both the retired Python compiler and `zakc` before the Python compiler
was removed. Programs print only ints, strings, and exactly representable
floats (such as `3.75`), never booleans, arrays, or maps, so the output does
not depend on map iteration order, float rounding, or container formatting.
`zakc/tests/fixtures.rs` also asserts that each program parses and passes
semantic checks in under 50 ms (PRD F2).


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

These tests have the `docker` marker. CI has no Docker, so it runs the other
zakc tests with `-m "not docker"`. Do the same locally without Docker:

```sh
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests -q -m "not docker"
```

`test_conformance.py` uses the native `zakc.zak_transpile` binding and checks
emitted Python against Python 3.12 grammar compatibility. It executes each
of the 40 fixture programs through `sandbox.runner.execute_program` and
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
