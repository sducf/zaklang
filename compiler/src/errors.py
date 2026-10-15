"""Public diagnostic/result types shared by compiler consumers."""

from dataclasses import dataclass

from .ast import Program


@dataclass(frozen=True)
class CompileError:
    line: int
    col: int
    code: str
    message: str


@dataclass(frozen=True)
class CompileResult:
    ok: bool
    ast: Program | None
    errors: list[CompileError]
