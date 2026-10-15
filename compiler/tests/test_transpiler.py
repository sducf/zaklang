"""Emission contracts and execution checks for trusted, hand-written examples."""

import builtins
from pathlib import Path
import subprocess
import sys

import pytest

from compiler.src import TranspileError, compile, transpile
from compiler.src.parser import parse


def emitted(source):
    """Compile and emit a trusted example, failing the test on static errors."""
    result = compile(source)
    assert result.ok and result.ast is not None, result.errors
    return transpile(result.ast)


def run_trusted(source, tmp_path):
    """Run emitted test code in a fresh child process with a five-second limit."""
    path = tmp_path / 'program.py'
    path.write_text(emitted(source), encoding='utf-8')
    result = subprocess.run([sys.executable, '-I', str(path)], cwd=tmp_path,
                            capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout.decode()


def test_exact_snapshot_for_typed_arithmetic():
    output = emitted('x:=7/2;y:=7.0/2.0;out(x);out(y)')
    expected = (Path(__file__).parent / 'snapshots/arithmetic.py.txt').read_text()
    assert output == expected
    builtins.compile(output, '<transpiled>', 'exec')


def test_exact_snapshot_for_function_and_control_flow():
    source = '@f(n:I)I{total:=0;~i:0..n{?i%2==0{total+=i}}^total}out(f(4))'
    output = emitted(source)
    expected = (Path(__file__).parent / 'snapshots/function.py.txt').read_text()
    assert output == expected
    builtins.compile(output, '<transpiled>', 'exec')


def test_repeated_emission_is_identical_and_independent():
    program = compile('a:=[1];out(a)').ast
    assert program is not None
    first = transpile(program)
    emitted('x:="unrelated";out(x)')
    assert transpile(program) == first
    assert emitted('a:=[1];out(a)') == first


@pytest.mark.parametrize('source,code', [
    ('out(missing)', 'UNDEFINED_NAME'),
    ('a:=[1];a<<T', 'TYPE_MISMATCH'),
    ('a:=[x~x:[1]]', 'UNSUPPORTED_FEATURE'),
])
def test_invalid_or_unsupported_ast_raises_structured_error(source, code):
    with pytest.raises(TranspileError) as caught:
        transpile(parse(source))
    assert code in [error.code for error in caught.value.errors]
    assert all(error.line > 0 and error.col > 0 for error in caught.value.errors)


@pytest.mark.parametrize('source,expected', [
    ('out(-7/2);out(7/-2);out(-7/-2);x:=-7;x/=2;out(x)', '-4\n-4\n3\n-4\n'),
    ('out(7.0/2.0);x:=7.0;x/=2.0;out(x)', '3.5\n3.5\n'),
    ('@f()B{out(99);^T}out(F&f());out(T|f());out(T?1:2)', 'False\nTrue\n1\n'),
    ('x:=1;?T{x:=2;out(x)}out(x);~x:0..2{out(x)}out(x)', '2\n1\n0\n1\n1\n'),
    ('x:=1;@f()I{x+=2;^x}out(f());out(x)', '3\n3\n'),
    ('x:=1;@f()I{?T{x:=2;out(x)}x+=3;^x}out(f());out(x)', '2\n4\n4\n'),
    ('@class(from:I)I{^from+1}lambda:=4;out(class(lambda))', '5\n'),
    ('@print(len:I)I{^len+1}list:=4;out(print(list));out(#"abc")', '5\n3\n'),
    ('@fact(n:I)I{?n<2{^1}^n*fact(n-1)}out(fact(5))', '120\n'),
    ('out(f(2));@f(n:I)I{^g(n)}@g(n:I)I{^n+1}', '3\n'),
    ('a:=[7];@idx()I{out(99);^0}a[idx()]/=2;out(a[0])', '99\n3\n'),
    ('s:="abc";out(s[:2]);out(s[1:]);out(s[:]);out(s[-1])', 'ab\nbc\nabc\nc\n'),
    ('m:{S:I}={"a":1};~k,v:m{out(k);out(v)}out("a"@m)', 'a\n1\nTrue\n'),
    ('out(I(2.9));out(R(2));out(S(2));out(B(0));out(B("x"))', '2\n2.0\n2\nFalse\nTrue\n'),
    ('a:=[3,1,2];out(srt(a));out(rev(a));out(a);out(pop(a));a<<4;out(a)', '[1, 2, 3]\n[2, 1, 3]\n[3, 1, 2]\n2\n[3, 1, 4]\n'),
    ('out(abs(-2));out(min(3,1));out(max(3.0,1.0));out(sum([1,2]));a:[R]=[];out(sum(a))', '2\n1\n3.0\n3\n0.0\n'),
    ('m:{S:I}={"x":1};out(keys(m));out(vals(m));del(m,"x");out(m)', "['x']\n[1]\n{}\n"),
    ('out(spl("a b"," "));out(jn([],","));out(jn(["a","b"],":"));out(up("a"));out(lo("B"))', "['a', 'b']\n\na:b\nA\nb\n"),
    ('i:=0;~i<5{i+=1;?i==2{>}?i==4{!}out(i)}out(i)', '1\n3\n4\n'),
    ('a:[[I]]=[[]];a[0]<<2;a[0][0]+=3;out(a)', '[[5]]\n'),
    ('m:{S:[I]}={"x":[7]};m["x"][0]/=2;out(m)', "{'x': [3]}\n"),
    ('@a()[S]{out(1);^["a","b"]}@d()S{out(2);^":"}out(jn(a(),d()))', '1\n2\na:b\n'),
])
def test_trusted_examples_preserve_semantics(source, expected, tmp_path):
    assert run_trusted(source, tmp_path) == expected
