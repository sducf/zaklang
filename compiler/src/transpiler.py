"""Public deterministic Python emission for the statically checked SD1 AST."""

from .ast import Program
from .errors import CompileError
from .python_emitter import PythonEmitter
from .semantic import analyze


class TranspileError(ValueError):
    """The input AST cannot be emitted; ``errors`` contains located diagnostics."""

    def __init__(self, errors: list[CompileError]):
        self.errors = errors
        super().__init__('; '.join(f'{error.code}: {error.message}' for error in errors))


def transpile(program: Program) -> str:
    """Validate and emit standalone Python without executing either language.

    Output is deterministic for a given AST on the same Python runtime.
    Names/parameters are lowered to collision-free internal identifiers;
    user functions are exported under their original names for positional calls.
    """
    try:
        analysis = analyze(program)
        if analysis.errors:
            raise TranspileError(analysis.errors)
        return PythonEmitter(program, analysis).emit()
    except RecursionError as error:
        raise TranspileError([CompileError(program.span.line, program.span.col, 'COMPLEXITY_LIMIT',
                                          'Source nesting exceeds the transpiler limit.')]) from error
