"""Public Zak static compiler interface."""

from .ast import Program
from .errors import CompileError, CompileResult
from .main import compile

__all__ = ["compile", "CompileError", "CompileResult", "Program"]
