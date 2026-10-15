"""Parse the checked-in Lark grammar into the public Zak AST."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from lark import Lark, Transformer, v_args

from . import ast as a


@lru_cache(maxsize=1)
def _parser() -> Lark:
    """Build the grammar parser once; retain positions and optional-field slots."""

    # The text file literally has a representation of the grammar, so don't remove it
    return Lark(
        Path(__file__).with_name("grammar.txt").read_text(encoding="utf-8"),
        parser="lalr", start="start", propagate_positions=True,
        maybe_placeholders=True,
    )


def _span(meta) -> a.Span:
    """Convert Lark positions to public spans, defaulting empty input to 1:1."""
    return a.Span(getattr(meta, "line", 1), getattr(meta, "column", 1),
                  getattr(meta, "end_line", 1), getattr(meta, "end_column", 1))


@v_args(meta=True)
class _AST(Transformer):
    """Map grammar-rule callbacks to immutable compiler-owned syntax nodes.

    Most methods directly mirror their rule's children. Optional grammar
    slots remain None so missing types and slice endpoints stay distinguishable.
    """

    def start(self, meta, children):
        return a.Program(tuple(children[0]), span=_span(meta))

    def seq(self, meta, children):
        return tuple(children)

    def block(self, meta, children):
        return children[0]

    def prim(self, meta, children):
        return a.PrimitiveType(str(children[0]))

    def arr_t(self, meta, children):
        return a.ArrayType(children[0])

    def map_t(self, meta, children):
        return a.MapType(*children)

    def param(self, meta, children):
        return a.Parameter(str(children[0]), children[1], span=_span(meta))

    def fn(self, meta, children):
        """Separate the optional parameter slots from the return type and body."""
        
        return a.Function(
            str(children[0]), 
            tuple(c for c in children[1:-2] if c is not None),
            children[-2], children[-1], span=_span(meta)
        )

    def decl(self, meta, children):
        return a.Declaration(
            str(children[0]), 
            children[1], 
            children[2],
            span=_span(meta)
        )

    def target(self, meta, children):
        """Build a variable-rooted chain of indexed assignment targets."""
        
        name = children[0]
        value = a.Name(str(name), span=a.Span(name.line, name.column, name.end_line, name.end_column))
        
        for index in children[1:]:
            value = a.Index(value, index, span=_span(meta))
        
        return value

    def aop(self, meta, children):
        return str(children[0])

    addop = mulop = cmpop = aop

    def assign(self, meta, children):
        return a.Assignment(*children, span=_span(meta))

    def push(self, meta, children):
        return a.Append(*children, span=_span(meta))

    def ret(self, meta, children):
        return a.Return(children[0], span=_span(meta))

    def brk(self, meta, children):
        return a.Break(span=_span(meta))

    def cont(self, meta, children):
        return a.Continue(span=_span(meta))

    def if_(self, meta, children):
        """Normalize an elif into an If node inside the parent's else sequence."""
        other = children[2]
        return a.If(children[0], children[1], (other,) if isinstance(other, a.If) else (other or ()), span=_span(meta))

    def while_(self, meta, children):
        return a.While(*children, span=_span(meta))

    def iter(self, meta, children):
        return a.Iteration(children[0], children[1], span=_span(meta))

    def for_(self, meta, children):
        """Preserve one or two loop names while dropping the unused name slot."""
        return a.For(tuple(str(c) for c in children[:-2] if c is not None), children[-2], children[-1], span=_span(meta))

    def int_lit(self, meta, children):
        return a.Literal(int(children[0]), a.I, span=_span(meta))

    def float_lit(self, meta, children):
        return a.Literal(float(children[0]), a.R, span=_span(meta))

    def str_lit(self, meta, children):
        return a.Literal(json.loads(str(children[0])), a.S, span=_span(meta))

    def true(self, meta, children):
        return a.Literal(True, a.B, span=_span(meta))

    def false(self, meta, children):
        return a.Literal(False, a.B, span=_span(meta))

    def var(self, meta, children):
        return a.Name(str(children[0]), span=_span(meta))

    def binop(self, meta, children):
        return a.Binary(*children, span=_span(meta))

    compare = binop

    def member(self, meta, children):
        return a.Binary(children[0], "@", children[1], span=_span(meta))

    def or_op(self, meta, children):
        return a.Binary(children[0], "|", children[1], span=_span(meta))

    def and_op(self, meta, children):
        return a.Binary(children[0], "&", children[1], span=_span(meta))

    def not_op(self, meta, children):
        return a.Unary("!", children[0], span=_span(meta))

    def neg(self, meta, children):
        return a.Unary("-", children[0], span=_span(meta))

    def length(self, meta, children):
        return a.Unary("#", children[0], span=_span(meta))

    def cond(self, meta, children):
        return a.Conditional(*children, span=_span(meta))

    def call(self, meta, children):
        return a.Call(str(children[0]), tuple(c for c in children[1:] if c is not None), span=_span(meta))

    def cast(self, meta, children):
        return a.Cast(*children, span=_span(meta))

    def index(self, meta, children):
        return a.Index(*children, span=_span(meta))

    def slice(self, meta, children):
        """Keep absent lower/upper bounds in place instead of compacting children."""
        return a.Slice(*children, span=_span(meta))

    def arr(self, meta, children):
        return a.Array(tuple(c for c in children if c is not None), span=_span(meta))

    def pair(self, meta, children):
        return tuple(children)

    def map(self, meta, children):
        return a.Map(tuple(c for c in children if c is not None), span=_span(meta))

    def comp(self, meta, children):
        return a.Comprehension(children[0], str(children[1]), children[2], children[3], span=_span(meta))


def parse(source: str) -> a.Program:
    """Return a syntax tree without semantic validation or source execution.

    Lark syntax/transform errors propagate; compile(source) converts them to
    structured diagnostics for API consumers and the static-checking CLI.
    """
    return _AST().transform(_parser().parse(source))
