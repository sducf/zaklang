from typing import final

@final
class CheckedProgram:
    """A Zak program that has passed parsing and semantic checking."""

@final
class CompilerError:
    """Compiler diagnostic type exported by the native module."""

@final
class TranspiledProgram:
    """Python generated from a checked Zak program."""

    @property
    def source(self) -> str: ...

def zak_check(source: str) -> CheckedProgram:
    """Check Zak source, raising ValueError with compiler diagnostics."""
    ...

def zak_transpile(source: str) -> TranspiledProgram:
    """Generate Python without executing it; raise ValueError on invalid Zak."""
    ...
