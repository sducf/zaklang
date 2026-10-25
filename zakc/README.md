# zakc — Rust compiler scratch

![I will review it later]

An uncommitted experiment alongside the existing Python compiler. Package,
library, and binary are named `zakc`. The compiler implementation is native
Rust; Python is used only by the comparison/benchmark harnesses and the
existing execution sandbox.

Read [ANALYSIS.md](ANALYSIS.md) for the migration assessment and tradeoffs.

## Try it

Run from the repository root:

```sh
cargo run --manifest-path zakc/Cargo.toml -- compiler/tests/conformance/011_recursion.zak
cargo run --manifest-path zakc/Cargo.toml -- --emit check compiler/tests/conformance zakbench/tasks
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
use zakc::{compile, compile_to_python};

let checked = compile("x:=7/2;out(x)").unwrap();
let generated = compile_to_python("x:=7/2;out(x)").unwrap();
assert!(!generated.python_ast.is_empty());
assert!(generated.source.contains("//"));
```

The staged interfaces are `parser::parse`, `semantic::check`, and
`transpiler::transpile`. `CheckedProgram` has a private constructor and exposes
immutable syntax/type metadata. The emitter accepts only `&CheckedProgram`.
`TranspiledProgram` contains Python source, a RustPython `ast::Suite`, and a
mapping from generated Python lines to Zak spans. No compile API executes code.

Node IDs are stable within one parsed program and remain valid when it moves.
Checking rejects duplicate IDs with `INVALID_AST`; independently parsed trees
cannot be concatenated without reassigning their IDs.

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

## Verify

```sh
cargo test --manifest-path zakc/Cargo.toml
cargo fmt --manifest-path zakc/Cargo.toml --check
cargo clippy --manifest-path zakc/Cargo.toml --all-targets -- -D warnings
cargo build --manifest-path zakc/Cargo.toml
.venv/bin/python zakc/compare.py --report zakc/verification.json
docker build -t zaklang-sandbox ./sandbox
.venv/bin/python zakc/compare.py --docker --report zakc/verification.json
```

The comparison harness extracts the existing test examples without editing
them. It compares acceptance and diagnostic-code sets against the Python
compiler, then syntax-checks Rust-generated Python with CPython. Docker mode
compares all 15 stdout fixtures, checks all 10 references against 69 hidden
cases, and executes all 22 existing transpiler runtime examples.

The Rust contracts cover spans, Unicode columns, arbitrary-size integer
literals, stable metadata, error context propagation, deterministic output,
the complete corpus, and regressions found in independent review.

## Small throughput experiment

```sh
cargo build --release --manifest-path zakc/Cargo.toml --example throughput
.venv/bin/python zakc/benchmark.py --report zakc/benchmark-results.json
```

Both pipelines parse, check, emit, and parse emitted Python, over the same 25
programs. Startup, file reads, and execution are excluded. This is a local
warm-process comparison, not an end-to-end benchmark of model inference or
Docker execution. See the JSON result and analysis for qualifications.

## Prototype limits

The parser conservatively limits input to 1 MB, delimiter nesting to 32,
consecutive unary operators to 128, and total `?` markers outside strings to 128. The AST/checker also applies a depth budget of 128. Small host thread
stacks use `stacker` to provide a bounded larger stack for recursive stages.
These budgets are deliberately conservative, including for wide programs;
they are not language-spec limits. Grammar/parser edge-case equivalence and
production resource budgets need further work before replacing the service.
