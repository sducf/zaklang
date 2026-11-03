# ZakLang compiler (legacy Python implementation)

The SD-32 compiler parses Zak source and checks names, types, and control
flow. The separate SD-34 transpiler turns its compiler-owned AST into
standalone Python. Neither API executes Zak or the emitted Python.

## Install and check files

Use Python 3.12 or newer, from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r compiler/requirements-dev.txt
.venv/bin/python -m compiler.src zakc/tests/conformance zakbench/tasks
.venv/bin/pyright --project compiler/pyrightconfig.json
```

The compiler test suite has moved to `zakc/tests` and exercises the native
Rust implementation and its Python bindings. See [the complete test commands](../zakc/README.md#run-all-tests).
Pyright separately checks this legacy implementation in `compiler/src`.
Pyright requires Node.js.
For editor diagnostics, select the repository-root `.venv/bin/python`
interpreter. The compiler-specific Pyright configuration uses that environment
and checks against Python 3.12 without changing the backend's configuration.

Supply individual `.zak` paths or directories (searched recursively).
Successful files print `path: OK`; errors print
`path:line:column: CODE: message`. All files are checked even if one fails.
Exit codes: 0 means all files passed, 1 means a compilation/read failure,
and 2 means invalid command arguments or no files found. Add `--json` for a
JSON array of `{path, ok, errors}` objects. Source programs are never run.
Runtime-only consumers can install `compiler/requirements.txt` instead.

## Python interface

```python
from compiler.src import compile

result = compile('x:=3;out(x)')
if result.ok:
    program = result.ast
    for statement in program.statements:
        print(type(statement).__name__, statement.span)
else:
    for error in result.errors:
        print(error.line, error.col, error.code, error.message)
```

`CompileResult` contains `ok: bool`, `ast: Program | None`, and
`errors: list[CompileError]`. Failures return no AST; success has no errors.
`CompileError` has one-based `line` and `col`, `code`, and `message`.
Ordinary compiler failures return diagnostics. `KeyboardInterrupt` and
`SystemExit` propagate. Syntax errors stop parsing; semantic errors accumulate
across independently checkable statements.

## Transpile to Python (SD-34)

```python
from pathlib import Path
from compiler.src import compile, transpile

result = compile(Path('zakbench/tasks/array_sum/reference.zak').read_text())
if result.ok:
    Path('reference.py').write_text(transpile(result.ast), encoding='utf-8')
else:
    print(result.errors)
```

`transpile(program: Program) -> str` revalidates the AST and raises
`TranspileError` with an `errors: list[CompileError]` for invalid or
unsupported input. It produces deterministic source on the same Python
runtime, ending in a newline, with no third-party runtime dependencies.
The static diagnostics command and `compile(source)` do not emit code.

The emitter preserves lexical block bindings, short-circuit logic, and
single evaluation of indexed update targets. Integer `/` and `/=` become
floor division; R uses ordinary division. Functions are defined before
top-level statements to support forward calls. Variables and internal
function names use uppercase `_ZAK_` prefixes that Zak names cannot collide
with. User functions are exported under their original names, including
`solve`, for positional calls; generated parameter names are internal.
Function assignments to module bindings use Python `global` declarations.

All documented builtins are lowered to qualified Python builtins or
container/string operations. `out` uses Python print formatting and a final
newline. `srt`, `rev`, `keys`, and `vals` return arrays rather than iterators;
`sum` on an empty R array returns `0.0`. The generated join helper preserves
left-to-right evaluation of `jn(values, delimiter)` arguments.

`semantic.analyze(program)` exposes `AnalysisResult(errors,
expression_types)` for compiler stages. Types are keyed by `id(node)` and
are meaningful only while that exact AST is alive. Failed analyses have
partial metadata; code emission refuses them. The AST itself is unchanged.

## Internal pipeline

1. [parser.py](src/parser.py) loads the grammar once and transforms Lark trees
   into [AST dataclasses](src/ast.py). Most transformer callbacks directly
   mirror their grammar rules; optional fields and source positions remain
   explicit in the resulting nodes.
2. [semantic.py](src/semantic.py) registers function signatures, checks
   lexical scopes and strict types, and conservatively validates return
   paths. Its internal diagnostic exception stops a failed statement while
   allowing independent statements to be checked. Successful expression
   types are retained for downstream stages.
3. [main.py](src/main.py) exposes `compile(source)`, translating parsing and
   analysis failures into public results. Its command-line entry point only
   performs static checks; it never runs the programs.
4. [transpiler.py](src/transpiler.py) validates the supplied AST again and
   refuses to emit code when analysis returns diagnostics. The private
   [Python emitter](src/python_emitter.py) resolves bindings in source order,
   constructs Python AST nodes, and renders a standalone module with helper
   definitions, hoisted functions, executable statements, and public function
   aliases.

Emitter methods construct code rather than evaluate it. Runtime argument
order, short circuiting, and augmented assignment behavior are delegated to
the corresponding Python AST nodes. Generated uppercase names keep internal
bindings distinct from all names that Zak's grammar permits.

## AST contract for SD-34

Import node classes from `compiler.src.ast`. Nodes are frozen dataclasses,
sequences are tuples, and every node has a `Span(line, col, end_line,
end_col)` with exclusive end positions. No Lark objects escape the parser.
`Program.statements` holds statements in source order.

- Statements: `Declaration(name, declared_type, value)`,
  `Assignment(target, operator, value)`, `Append(target, value)`,
  `Return(value)`, `Break`, `Continue`, `Call(name, arguments)`,
  `Function(name, parameters, return_type, body)`,
  `If(condition, then_body, else_body)`, `While(condition, body)`, and
  `For(names, iteration, body)`. Parameters have `name` and `type`.
- Expressions: `Literal(value, type)`, `Name(name)`,
  `Unary(operator, operand)`, `Binary(left, operator, right)`,
  `Conditional(condition, then_value, else_value)`, `Call`, `Cast(type, value)`,
  `Index(collection, index)`, `Slice(collection, lower, upper)`,
  `Array(elements)`, `Map(entries)`, and `Comprehension`.
- `Iteration(start, stop)` represents `start..stop` when `stop` is present;
  otherwise `start` is the collection expression. Missing slice endpoints
  remain `None`. An `elif` is an `If` in its parent's `else_body`.
- Types: `PrimitiveType(name)` (constants `I`, `R`, `B`, `S`),
  `ArrayType(element)`, and `MapType(key, value)`.

`parser.parse(source)` exposes syntax-only parsing for tools and spec
examples; it can raise Lark exceptions. Only `compile(source)` guarantees
structured diagnostics. Parsing a feature does not imply semantic support.

## Static rules and supported subset

The existing `src/grammar.txt` remains the syntax source of truth. Supported
constructs cover all 15 SD-35 fixtures and the three sample Zak references:
variables, assignments, arithmetic, conditions, loops, functions/recursion,
arrays, strings, and maps. Comprehensions parse but produce
`UNSUPPORTED_FEATURE`; nested function declarations are also unsupported.

Types are strict: `I`, `R`, and `B` never implicitly mix. Casts `I(x)`,
`R(x)`, `S(x)`, and `B(x)` accept primitive values; whether a particular string
can be converted at runtime is not proven. Arithmetic requires matching
numeric types; `+` also concatenates matching arrays or strings. `I/I`
retains `I` (the transpiler must implement floor division). Conditions are B.
Empty collections need context, such as an explicit declaration, assignment,
function argument, or return type. Maps have I or S keys.

Declarations use lexical block scopes. Assignments update enclosing bindings.
Loop variables stay in their loop. Functions are top-level; signatures are
registered before body checking for recursive and forward calls. Function
bodies can reference globals declared before the function definition. Names
of functions and builtins cannot be rebound. Functions must return the
specified type on every path; loops alone do not establish guaranteed return.
String mutation is rejected; array/string indices and slice bounds require I.

Builtin signatures (`N` is either I or R, `T` is a consistent element type):

| Builtin | Signature |
| --- | --- |
| `out` | `(T) -> void` |
| `abs` | `(N) -> N` |
| `min`, `max` | `(N, N) -> N` |
| `sum` | `([N]) -> N` |
| `srt` | `([T]) -> [T]`, T is I, R, or S |
| `rev` | `([T]) -> [T]` |
| `pop` | `([T]) -> T` |
| `keys`, `vals` | `({K:V}) -> [K]` / `[V]` |
| `del` | `({K:V}, K) -> void` |
| `spl` | `(S, S) -> [S]` |
| `jn` | `([S], S) -> S` |
| `up`, `lo` | `(S) -> S` |

Void calls can be statements but cannot be used as values.

## Diagnostics

| Code | Meaning |
| --- | --- |
| `SYNTAX_ERROR` | Input does not match the grammar |
| `INVALID_LITERAL` | Invalid string escape or numeric literal |
| `UNDEFINED_NAME` | Variable or function is unknown |
| `DUPLICATE_NAME` | Name redeclared in the same scope |
| `RESERVED_NAME` | Binding conflicts with a function or builtin |
| `CALL_ARITY` | Wrong number of arguments |
| `TYPE_MISMATCH` | Incompatible types or operation |
| `INVALID_TYPE` | Invalid declared collection type |
| `CANNOT_INFER_TYPE` | Empty collection lacks type context |
| `INVALID_TARGET` | Mutation of an immutable value |
| `INVALID_ITERATION` | Invalid iterator or loop binding count |
| `INVALID_CONTROL_FLOW` | Return/break/continue outside their context |
| `MISSING_RETURN` | Function may fall through without returning |
| `UNSUPPORTED_FEATURE` | Grammar feature outside the SD1 compiler subset |
| `COMPLEXITY_LIMIT` | Source nesting exceeds analysis capacity |
| `INTERNAL_ERROR` | Unexpected compiler defect; analysis failed |
| `IO_ERROR` | CLI cannot read the source file |

## Limits and executable conformance

Passing these checks does not prove runtime safety or correct output. They
cannot establish termination, index bounds, map-key existence, divisor
nonzero, or hidden-test correctness. Runtime execution and exact stdout
comparison are checked separately through the Docker sandbox.

The [conformance fixtures](../zakc/tests/conformance/README.md) and all compiler
tests now live in `zakc`. The native suite checks the Rust AST, semantic
metadata, diagnostics, CLI, and generated Python AST and snapshots. Python
binding tests execute trusted examples in subprocesses, and the Docker suite
checks isolated stdout and reference grading. Follow [zakc's test instructions](../zakc/README.md#run-all-tests)
for setup and the exact commands to run every suite.
