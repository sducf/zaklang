# zakc — Rust compiler

The Zak compiler, written in Rust. It replaced the original Python (Lark)
compiler, which was removed after the measurements in
[the benchmark report](../docs/benchmarks/compiler-comparison/REPORT.md).
Package, library, and binary are named `zakc`. Python bindings are enabled
with `--features python` and are what the backend, sandbox, and ZakBench use;
normal Cargo builds, tests, and examples do not depend on Python or libpython.

Read [ANALYSIS.md](ANALYSIS.md) for the migration assessment and tradeoffs.

## Try it

Run from the repository root:

```sh
cargo run --manifest-path zakc/Cargo.toml -- zakc/tests/conformance/011_recursion.zak
cargo run --manifest-path zakc/Cargo.toml -- --emit check zakc/tests/conformance zakbench/tasks
cargo run --manifest-path zakc/Cargo.toml -- --emit zak-ast zakbench/tasks/array_sum/reference.zak
cargo run --manifest-path zakc/Cargo.toml -- --emit python-ast zakbench/tasks/array_sum/reference.zak
cargo run --manifest-path zakc/Cargo.toml -- --json --emit check path/to/program.zak
```

Default output is standalone Python. `--emit check` performs parsing and
semantic validation without emitting or executing code. `--emit zak-ast`
prints the checked Zak syntax as JSON. `--emit python-ast` prints the owned
RustPython AST with Rust's debug formatter. `--json` produces an array of
per-file results; errors include codes, Zak spans, and Rust call-site traces.
Use `-` as the input path to read stdin. Directories are searched recursively
for `.zak` files. Failures exit with code 1.

## Library

```rust
use zakc::{zak_check, zak_transpile};

let checked = zak_check("x:=7/2;out(x)").unwrap();
let generated = zak_transpile("x:=7/2;out(x)").unwrap();
assert!(!generated.python_ast.is_empty());
assert!(generated.source.contains("//"));
```

The staged interfaces are `parser::parse`, `Program::check`, and
`CheckedProgram::transpile`. `CheckedProgram` has a private constructor and exposes
immutable syntax/type metadata. The emitter accepts only `&CheckedProgram`.
`TranspiledProgram` contains Python source, a RustPython `ast::Suite`, and a
mapping from generated Python lines to Zak spans. No compile API executes code.

Node IDs are stable within one parsed program and remain valid when it moves.
Checking rejects duplicate IDs with `INVALID_AST`; independently parsed trees
cannot be concatenated without reassigning their IDs.

## Python bindings

The Python module exports `zak_check(source)` and `zak_transpile(source)`.
They return `CheckedProgram` and `TranspiledProgram` objects respectively;
the latter exposes generated Python through its read-only `source` property.
Invalid programs raise `zakc.ZakCompileError` (a `ValueError` subclass). Its
`errors` list holds one `CompilerError` per diagnostic with read-only `code`,
`message`, `line`, `col`, `end_line`, and `end_col` (one-based characters;
1:1 when an error has no source location). `str(error)` is the full text,
including Rust call-site traces; `message` omits them and is what the
backend sends to the model. Both functions release the GIL while compiling.

Install the extension into the current environment (maturin builds it with
the release profile; a Rust toolchain is required):

```sh
pip install ./zakc
```

The backend's `requirements.txt` does this through `../zakc`.
The bindings are opt-in; the default Rust library, CLI, tests, and throughput
example build without linking libpython. On Unix, set
`PYO3_BUILD_EXTENSION_MODULE=1` when building the Python extension so it uses
the interpreter's Python symbols instead of linking an embedding library.

For a manual Linux build, run from the repository root:

```sh
PYO3_BUILD_EXTENSION_MODULE=1 cargo build --manifest-path zakc/Cargo.toml --features python --lib
mkdir -p zakc/target/python
cp zakc/target/debug/libzakc.so zakc/target/python/zakc.so
cp zakc/zakc.pyi zakc/target/python/zakc.pyi
PYTHONPATH=zakc/target/python python3 zakc/tests/python_bindings.py
```

With that directory on `PYTHONPATH`, Python callers can use:

```python
import zakc

checked = zakc.zak_check("x:=7/2;out(x)")
generated = zakc.zak_transpile("x:=7/2;out(x)")
print(generated.source)
```

The `zakc/zakc.pyi` stub describes the Python-visible API for autocomplete and
static type checking. The repository's `pyrightconfig.json` includes `zakc`
in `extraPaths`, so Pyright and Pylance can resolve the stub while editing.
When distributing the extension manually, keep `zakc.pyi` beside `zakc.so`
(or the platform's corresponding extension file). Use a normal `import zakc`
so the language server can resolve the signatures statically.

## Errors and context

`error.rs` adapts the SaúdeBridge `ErrorContext` pattern:

```rust
use zakc::{ErrorCode, ErrorContext};
use zakc::ast::Span;

fn example(path: &std::path::Path) -> Result<String, zakc::CompilerError> {
    std::fs::read_to_string(path)
        .trace_ctx(("reading Zak source", ErrorCode::IoError))
        .at(Span::point(1, 1))
}
```

`trace`, `trace_ctx`, and `trace_at` work on `Option<T>` and on
`Result<T, E>` where `E: Into<CompilerError>`, including existing compiler
errors. `at` attaches the source location while preserving an existing inner
location. `trace_ctx` accepts a message or `(message, ErrorCode)`.

`CompilerError.span` identifies the Zak source with one-based character
line/column and zero-based UTF-8 byte ranges (exclusive end). `sources`
identifies Rust file/line/column through `#[track_caller]`, with optional
context messages. These two coordinate systems are intentionally separate.
`derive_more`, `strum`, and `thiserror` derive displays, enum conversions,
variant iteration, and error implementations. There are no manual `Display`
implementations.

## Run all tests

Run the following from the **repository root** on Linux/WSL. Install Rust,
Python 3.12 or newer with `venv`/pip, and Node.js (required by Pyright).
The complete suite also requires Docker running with WSL integration enabled
when applicable. The image is built by the command below.

```sh
# Install Python test and type-checking tools.
python3 -m venv .venv
.venv/bin/python -m pip install -r zakc/requirements-dev.txt

# All native tests: AST/parser, metadata, semantics, CLI, snapshots, and fixtures.
cargo test --manifest-path zakc/Cargo.toml

# Build the optional Python extension for the test interpreter.
PYO3_PYTHON="$PWD/.venv/bin/python" PYO3_BUILD_EXTENSION_MODULE=1 \
  cargo build --manifest-path zakc/Cargo.toml --features python --lib
mkdir -p zakc/target/python
cp zakc/target/debug/libzakc.so zakc/target/python/zakc.so
cp zakc/zakc.pyi zakc/target/python/zakc.pyi

# All Python tests, including bindings, runtime corpus, and Docker conformance.
docker build -t zaklang-sandbox ./sandbox
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests -q

# Type checking, formatting, and linting for both build modes.
.venv/bin/pyright --project zakc/pyrightconfig.json
cargo fmt --manifest-path zakc/Cargo.toml --check
cargo clippy --manifest-path zakc/Cargo.toml --all-targets -- -D warnings
PYO3_PYTHON="$PWD/.venv/bin/python" PYO3_BUILD_EXTENSION_MODULE=1 \
  cargo clippy --manifest-path zakc/Cargo.toml --features python --lib -- -D warnings
```

`pytest.ini` also collects `tests/python_bindings.py`, so the pytest command
includes all four binding contracts. Native tests read the actual Rust AST,
checked type metadata, and RustPython AST; all 107 distinct parameterized
legacy source examples and all 22 runtime examples are preserved. The two
legacy tests that monkeypatched Python parser exceptions were specific to
the retired Python test implementation; the Rust suite checks native
diagnostics and that checking never executes source instead.

For local development without Docker, after building the extension above:

```sh
cargo test --manifest-path zakc/Cargo.toml
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests --ignore=zakc/tests/conformance -q
```

Docker-only tests can be rerun with:

```sh
PYTHONPATH="$PWD/zakc/target/python:$PWD" \
  .venv/bin/python -m pytest -c zakc/pytest.ini zakc/tests/conformance -q
```

Docker tests fail when Docker or the image is unavailable. They execute the
15 exact stdout fixtures plus the three sample references through the
existing isolated evaluator. Trusted subprocess tests separately execute all
15 fixtures, all discovered benchmark references (currently 50), and the 22
runtime examples. Missing references fail the native fixture/signature checks.

### Performance

The release profile uses fat LTO and one codegen unit. See
[the benchmark report](../docs/benchmarks/compiler-comparison/REPORT.md) for
the comparison with the retired Python compiler. Native throughput over the
discovered corpus (startup, file reads, and execution excluded):

```sh
cargo build --release --manifest-path zakc/Cargo.toml --example throughput
zakc/target/release/examples/throughput 200
```

## Prototype limits

The parser conservatively limits input to 1 MB, delimiter nesting to 32,
consecutive unary operators to 128, and total `?` markers outside strings to 128. The AST/checker also applies a depth budget of 128. Small host thread
stacks use `stacker` to provide a bounded larger stack for recursive stages.
These budgets are deliberately conservative, including for wide programs;
they are not language-spec limits. The total `?` budget in particular rejects
otherwise valid programs with more than 128 conditionals or ternaries
(roughly 10 KB of typical task code); real benchmark solutions are far below
it, but it is a known difference from the retired Python compiler. Span
coordinates come from a line index built once per parse, so per-node cost does
not depend on the source length.
