from typing import final

@final
class CheckedProgram:
    """A Zak program that has passed parsing and semantic checking."""

@final
class CompilerError:
    """One compiler diagnostic. Coordinates are one-based characters; errors
    without a Zak source location report line and column 1."""

    @property
    def code(self) -> str:
        """Stable diagnostic code, such as ``SYNTAX_ERROR`` or ``UNDEFINED_NAME``."""
        ...
    @property
    def message(self) -> str: ...
    @property
    def line(self) -> int: ...
    @property
    def col(self) -> int: ...
    @property
    def end_line(self) -> int: ...
    @property
    def end_col(self) -> int: ...

class ZakCompileError(ValueError):
    """Raised for invalid Zak source. ``str()`` holds the full diagnostics text."""

    errors: list[CompilerError]

@final
class TranspiledProgram:
    """Python generated from a checked Zak program."""

    @property
    def source(self) -> str: ...

def zak_check(source: str) -> CheckedProgram:
    """Check Zak source, raising ZakCompileError with compiler diagnostics."""
    ...

def zak_transpile(source: str) -> TranspiledProgram:
    """Generate Python without executing it; raise ZakCompileError on invalid Zak."""
    ...
