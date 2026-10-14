# SD-32: Zak parser, AST, and structured errors

## Outcome and scope

Implement the compiler front end described by SD-32 so SD-34 can consume a
stable AST and SD-35 can compile its fixtures. The existing grammar remains
the syntax source of truth. No transpiler, execution service, API endpoint,
or Jira reassignment is included.

## Approach

Use Lark's LALR parser, transform its tree into explicit Python dataclasses,
then run a separate semantic pass. Passing Lark trees directly to the
transpiler would couple consumers to grammar internals; building a custom
parser would duplicate the existing grammar. Dataclasses provide the smallest
clear interface between the two compiler tickets.

## Public interface and modules

`compiler.src` exports `compile(source: str) -> CompileResult`, `CompileResult`,
`CompileError`, and `Program`. `CompileResult` contains `ok: bool`,
`ast: Program | None`, and `errors: list[CompileError]`. Success returns an AST
and no errors; failure returns no AST and one or more errors.

`CompileError` contains one-based `line` and `col`, a stable machine-readable
`code`, and a concise `message`. Syntax and semantic errors have distinct
codes. The compiler returns errors for malformed source rather than raising.
An unexpected internal exception becomes a distinct internal-error result;
process-control exceptions are not swallowed.

- `ast.py`: source spans, primitive/array/map types, program, statements,
  expressions, function parameters, and iteration nodes.
- `parser.py`: cached Lark parser and parse-tree transformation, preserving
  positions, operators, and optional slice endpoints.
- `semantic.py`: scopes, function signatures, expression types, and checks.
- `errors.py`: result and diagnostic dataclasses.
- `main.py`: compilation orchestration; retain an executable entry point.

AST nodes distinguish declarations, assignments (including their operator),
append, return, break, continue, expression statements, functions, branches,
while loops, and iteration loops. Expressions distinguish literals, names,
unary/binary operations, comparisons, membership, conditional expressions,
calls, casts, indexing, slicing, arrays, and maps. ASTs carry source locations
and explicit declared types; semantic analysis does not replace them with
Python code or expose Lark objects.

## Semantic rules

Support the SD1 subset and the strings/maps used by the sample tasks.
Predeclare top-level function signatures to support recursion and forward
function calls. Reject duplicate declarations in a scope, undefined names,
wrong call arity, incompatible assignments/returns, and invalid operations.
Function parameters are local; branch/loop declarations use lexical child
scopes, while assignments resolve enclosing bindings. Loop variables are
local to their loop. Function definitions are top-level only for this subset.

Keep I, R, B, and S distinct: no implicit conversion, including bool/int.
Numeric operations require matching numeric types; integer division retains
I. Conditions and logical operators require B. Addition also supports S and
arrays of matching element types. Arrays are homogeneous; maps have I or S
keys and homogeneous values. Empty containers require contextual types from
a declaration, parameter, return, or other typed expression.

Check array/string indices and slice bounds as I, map indices against their
key type, and reject string mutation. Validate append, membership, range
bounds, array/string/map iteration, and key/value map iteration. Reject
return outside functions and break/continue outside loops. Check that every
function path returns its declared type; a loop alone does not establish a
guaranteed return. Explicit casts are the only type conversion mechanism.

Implement signatures for builtins needed by the fixtures and sample tasks,
including out and spl; document supported signatures. Unsupported builtins
and comprehensions produce explicit unsupported-feature diagnostics. The
grammar-header comprehension example must still parse to an AST, although
compilation reports its out-of-scope semantic feature.

## Validation

- Parse all four grammar-header examples into dataclass ASTs; verify tree
  shape, precedence, source positions, and omitted slice bounds.
- Compile all 15 SD-35 programs and all three Zak references successfully.
- Include at least ten invalid programs covering syntax, undefined names,
  arity, type mismatches, collections, and invalid control flow. Assert
  diagnostic codes and locations, not just failure flags.
- Cover recursion, function returns, scopes, explicit casts, and supported
  builtins; verify malformed source returns diagnostics without exceptions.
- Run the complete compiler tests and measure warmed compilation against
  SD-32's 50 ms per-program target, reporting cold parser startup separately.

## Handoff and limits

Document AST imports and a compile example for SD-34. Grammar validity is
separate from semantic acceptance: unsupported grammar features can have AST
representations without being in the SD1 compiler subset. SD-35 execution
and hidden-test correctness remain dependent on SD-34 and sandbox support.
Use a separate SD-32 development branch and preserve the existing local
`.gitignore` edit and SD-35 commit.
