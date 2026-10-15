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
    addition = declaration.value
    assert isinstance(addition, ast.Binary)
    assert addition.operator == "+"
    multiplication = addition.right
    assert isinstance(multiplication, ast.Binary)
    assert multiplication.operator == "*"
    assert isinstance(multiplication.right, ast.Literal)
    assert multiplication.right.value == 4


@pytest.mark.parametrize("source,lower,upper", [("a[:2]", None, 2), ("a[1:]", 1, None), ("a[:]", None, None)])
def test_slice_preserves_missing_endpoints(source, lower, upper):
    declaration = parse(f"x:={source}").statements[0]
    assert isinstance(declaration, ast.Declaration)
    value = declaration.value
    assert isinstance(value, ast.Slice)
    assert value.lower is None or isinstance(value.lower, ast.Literal)
    assert value.upper is None or isinstance(value.upper, ast.Literal)
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
    function = parse(examples[2]).statements[0]
    assert isinstance(function, ast.Function)
    returned = function.body[0]
    assert isinstance(returned, ast.Return)
    comprehension = returned.value
    assert isinstance(comprehension, ast.Comprehension)


def test_empty_literals_and_nested_types():
    statements = parse("a:[[I]]=[[]];m:{S:I}={}").statements
    array_decl, map_decl = statements
    assert isinstance(array_decl, ast.Declaration)
    assert isinstance(map_decl, ast.Declaration)
    assert array_decl.declared_type == ast.ArrayType(ast.ArrayType(ast.I))
    assert isinstance(array_decl.value, ast.Array)
    nested_array = array_decl.value.elements[0]
    assert isinstance(nested_array, ast.Array)
    assert nested_array.elements == ()
    assert map_decl.declared_type == ast.MapType(ast.S, ast.I)
    assert isinstance(map_decl.value, ast.Map)
    assert map_decl.value.entries == ()


def test_assignment_operator_and_iteration_names():
    statements = parse("m[k]+=1;~k,v:m{out(v)}").statements
    assignment, loop = statements
    assert isinstance(assignment, ast.Assignment)
    assert assignment.operator == "+="
    assert isinstance(assignment.target, ast.Index)
    assert isinstance(loop, ast.For)
    assert loop.names == ("k", "v")
