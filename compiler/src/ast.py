"""Zak's compiler-owned, immutable syntax tree (no Lark objects)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Span:
    line: int
    col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class PrimitiveType:
    name: str


@dataclass(frozen=True)
class ArrayType:
    element: Type


@dataclass(frozen=True)
class MapType:
    key: Type
    value: Type


Type = PrimitiveType | ArrayType | MapType
I, R, B, S = (PrimitiveType(name) for name in ("I", "R", "B", "S"))
VOID = PrimitiveType("void")


@dataclass(frozen=True, kw_only=True)
class Node:
    span: Span


@dataclass(frozen=True)
class Program(Node):
    statements: tuple[Statement, ...]


@dataclass(frozen=True)
class Literal(Node):
    value: int | float | bool | str
    type: Type


@dataclass(frozen=True)
class Name(Node):
    name: str


@dataclass(frozen=True)
class Unary(Node):
    operator: str
    operand: Expression


@dataclass(frozen=True)
class Binary(Node):
    left: Expression
    operator: str
    right: Expression


@dataclass(frozen=True)
class Conditional(Node):
    condition: Expression
    then_value: Expression
    else_value: Expression


@dataclass(frozen=True)
class Call(Node):
    name: str
    arguments: tuple[Expression, ...]


@dataclass(frozen=True)
class Cast(Node):
    type: Type
    value: Expression


@dataclass(frozen=True)
class Index(Node):
    collection: Expression
    index: Expression


@dataclass(frozen=True)
class Slice(Node):
    collection: Expression
    lower: Expression | None
    upper: Expression | None


@dataclass(frozen=True)
class Array(Node):
    elements: tuple[Expression, ...]


@dataclass(frozen=True)
class Map(Node):
    entries: tuple[tuple[Expression, Expression], ...]


@dataclass(frozen=True)
class Iteration(Node):
    start: Expression
    stop: Expression | None


@dataclass(frozen=True)
class Comprehension(Node):
    value: Expression
    name: str
    iteration: Iteration
    condition: Expression | None


Expression = Literal | Name | Unary | Binary | Conditional | Call | Cast | Index | Slice | Array | Map | Comprehension


@dataclass(frozen=True)
class Declaration(Node):
    name: str
    declared_type: Type | None
    value: Expression


@dataclass(frozen=True)
class Assignment(Node):
    target: Name | Index
    operator: str
    value: Expression


@dataclass(frozen=True)
class Append(Node):
    target: Name | Index
    value: Expression


@dataclass(frozen=True)
class Return(Node):
    value: Expression


@dataclass(frozen=True)
class Break(Node):
    pass


@dataclass(frozen=True)
class Continue(Node):
    pass


@dataclass(frozen=True)
class Parameter(Node):
    name: str
    type: Type


@dataclass(frozen=True)
class Function(Node):
    name: str
    parameters: tuple[Parameter, ...]
    return_type: Type
    body: tuple[Statement, ...]


@dataclass(frozen=True)
class If(Node):
    condition: Expression
    then_body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]


@dataclass(frozen=True)
class While(Node):
    condition: Expression
    body: tuple[Statement, ...]


@dataclass(frozen=True)
class For(Node):
    names: tuple[str, ...]
    iteration: Iteration
    body: tuple[Statement, ...]


Statement = Declaration | Assignment | Append | Return | Break | Continue | Function | If | While | For | Call
