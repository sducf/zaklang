# ZakLang compiler

The SD-32 compiler parses Zak source and checks names, types, and control
flow. It returns a compiler-owned AST for SD-34. It does not execute Zak or
emit Python.

## Install and check files

Use Python 3.12 or newer, from the repository root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r compiler/requirements-dev.txt
.venv/bin/python -m compiler.src compiler/tests/conformance zakbench/tasks
.venv/bin/python -m pytest compiler/tests
```

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

## Limits and conformance handoff

Passing these checks does not prove runtime safety or correct output. They
cannot establish termination, index bounds, map-key existence, divisor
nonzero, or hidden-test correctness. Runtime execution and exact stdout
comparison still depend on SD-34 and isolated execution support.

The [conformance directory](tests/conformance/README.md) has 15 programs and
expected stdout. Three task folders contain `reference.zak`. SD-32 checks
all 18 statically; SD-35 still needs to execute them after transpilation.
