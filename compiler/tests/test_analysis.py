"""Type metadata needed by the emitter, without mutating the public AST."""

from compiler.src import ast as a
from compiler.src.parser import parse
from compiler.src.semantic import analyze, check


def test_analysis_distinguishes_integer_and_real_division():
    program = parse('i:=7/2;r:=7.0/2.0')
    analysis = analyze(program)
    assert analysis.errors == []
    integer_decl, real_decl = program.statements
    assert isinstance(integer_decl, a.Declaration)
    assert isinstance(real_decl, a.Declaration)
    assert analysis.expression_types[id(integer_decl.value)] == a.I
    assert analysis.expression_types[id(real_decl.value)] == a.R


def test_contextual_nested_empty_array_type_is_retained():
    program = parse('a:[[I]]=[[]]')
    declaration = program.statements[0]
    assert isinstance(declaration, a.Declaration)
    value = declaration.value
    assert isinstance(value, a.Array)
    analysis = analyze(program)
    assert analysis.expression_types[id(value)] == a.ArrayType(a.ArrayType(a.I))
    assert analysis.expression_types[id(value.elements[0])] == a.ArrayType(a.I)


def test_assignment_target_and_void_call_types():
    program = parse('a:=[1];a[0]/=2;out(a)')
    analysis = analyze(program)
    assignment = program.statements[1]
    assert isinstance(assignment, a.Assignment)
    target = assignment.target
    assert isinstance(target, a.Index)
    assert analysis.expression_types[id(target)] == a.I
    assert analysis.expression_types[id(target.collection)] == a.ArrayType(a.I)
    assert analysis.expression_types[id(program.statements[2])] == a.VOID


def test_check_retains_analysis_diagnostics():
    program = parse('out(x);a:I=T')
    analysis = analyze(program)
    assert analysis.errors == check(program)
    assert [error.code for error in analysis.errors] == ['UNDEFINED_NAME', 'TYPE_MISMATCH']


def test_analysis_metadata_does_not_leak_between_calls():
    first = parse('x:=1')
    second = parse('x:=1.0')
    one, two = analyze(first), analyze(second)
    first_decl, second_decl = first.statements[0], second.statements[0]
    assert isinstance(first_decl, a.Declaration)
    assert isinstance(second_decl, a.Declaration)
    assert id(first_decl.value) not in two.expression_types
    assert one.expression_types[id(first_decl.value)] == a.I
    assert two.expression_types[id(second_decl.value)] == a.R
