"""AST contracts that the transpiler can consume without Lark internals."""

from pathlib import Path

import pytest

from compiler.src import ast
from compiler.src.parser import parse


def test_precedence_and_source_locations():
    program = parse("\nx:=2+3*4;out(x)")
    declaration = program.statements[0]
    assert isinstance(declaration, ast.Declaration)
    assert (declaration.span.line, declaration.span.col) == (2, 1)
    assert declaration.value.operator == "+"
    assert declaration.value.right.operator == "*"
    assert declaration.value.right.right.value == 4


@pytest.mark.parametrize("source,lower,upper", [("a[:2]", None, 2), ("a[1:]", 1, None), ("a[:]", None, None)])
def test_slice_preserves_missing_endpoints(source, lower, upper):
    value = parse(f"x:={source}").statements[0].value
    assert isinstance(value, ast.Slice)
    assert (value.lower.value if value.lower else None) == lower
    assert (value.upper.value if value.upper else None) == upper


def test_header_examples_parse_to_explicit_ast():
    grammar = (Path(__file__).parents[1] / "src/grammar.txt").read_text()
    examples = [line[5:] for line in grammar.splitlines() if line.startswith("//   @") and "   " not in line[5:]]
    assert len(examples) == 4
    for source in examples:
        function = parse(source).statements[0]
        assert isinstance(function, ast.Function)
        assert function.parameters[0].name
        assert function.return_type is not None
    comprehension = parse(examples[2]).statements[0].body[0].value
    assert isinstance(comprehension, ast.Comprehension)


def test_empty_literals_and_nested_types():
    statements = parse("a:[[I]]=[[]];m:{S:I}={}").statements
    assert statements[0].declared_type == ast.ArrayType(ast.ArrayType(ast.I))
    assert statements[0].value.elements[0].elements == ()
    assert statements[1].declared_type == ast.MapType(ast.S, ast.I)
    assert statements[1].value.entries == ()


def test_assignment_operator_and_iteration_names():
    statements = parse("m[k]+=1;~k,v:m{out(v)}").statements
    assert statements[0].operator == "+="
    assert isinstance(statements[0].target, ast.Index)
    assert statements[1].names == ("k", "v")
