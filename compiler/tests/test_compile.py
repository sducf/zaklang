"""Public API and diagnostic-command contracts; nothing executes Zak code."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from compiler.src import CompileError, CompileResult, Program, compile

ROOT = Path(__file__).resolve().parents[2]
CORPUS = sorted((ROOT / "compiler/tests/conformance").glob("*.zak")) + sorted((ROOT / "zakbench/tasks").glob("*/reference.zak"))


@pytest.mark.parametrize("path", CORPUS, ids=lambda p: str(p.relative_to(ROOT)))
def test_public_compile_accepts_corpus(path):
    result = compile(path.read_text())
    assert isinstance(result, CompileResult)
    assert result.ok and isinstance(result.ast, Program)
    assert result.errors == []


@pytest.mark.parametrize("source,code", [
    ('x:=', 'SYNTAX_ERROR'),
    ('x:=1\ny:=2', 'SYNTAX_ERROR'),
    ('X:=1', 'SYNTAX_ERROR'),
    ('out("unterminated)', 'SYNTAX_ERROR'),
    ('?T{out(1)', 'SYNTAX_ERROR'),
    ('@f(x:I)I{^x}out(f())', 'CALL_ARITY'),
    ('out(missing)', 'UNDEFINED_NAME'),
    ('x:I=F', 'TYPE_MISMATCH'),
    ('x:=1;x="s"', 'TYPE_MISMATCH'),
    ('m:{R:I}={}', 'INVALID_TYPE'),
    ('>', 'INVALID_CONTROL_FLOW'),
    ('^1', 'INVALID_CONTROL_FLOW'),
    ('x:=[]', 'CANNOT_INFER_TYPE'),
    ('@f()I{}', 'MISSING_RETURN'),
    ('a:=[i~i:0..3]', 'UNSUPPORTED_FEATURE'),
    ('out("\\q")', 'INVALID_LITERAL'),
])
def test_compile_returns_located_errors(source, code):
    result = compile(source)
    assert not result.ok and result.ast is None
    assert code in [error.code for error in result.errors]
    assert all(isinstance(error, CompileError) and error.line > 0 and error.col > 0 for error in result.errors)


def test_empty_program_is_valid():
    result = compile(' \n')
    assert result.ok and result.ast.statements == ()


def test_syntax_error_position():
    error = compile('x:=1;\ny:=?').errors[0]
    assert (error.line, error.col, error.code) == (2, 4, 'SYNTAX_ERROR')


def test_excessive_nesting_returns_a_diagnostic():
    result = compile('out(' + '-' * 2000 + '1)')
    assert not result.ok and result.errors[0].code == 'COMPLEXITY_LIMIT'


def test_internal_failure_is_distinct_and_does_not_expose_exception(monkeypatch):
    main = importlib.import_module('compiler.src.main')
    def broken_parse(source):
        raise RuntimeError('private implementation detail')
    monkeypatch.setattr(main, 'parse', broken_parse)
    result = compile('out(1)')
    assert result.errors[0].code == 'INTERNAL_ERROR'
    assert 'private' not in result.errors[0].message


def test_process_control_exceptions_are_not_swallowed(monkeypatch):
    main = importlib.import_module('compiler.src.main')
    def interrupted(source):
        raise KeyboardInterrupt
    monkeypatch.setattr(main, 'parse', interrupted)
    with pytest.raises(KeyboardInterrupt):
        compile('out(1)')


def command(*arguments):
    return subprocess.run([sys.executable, '-m', 'compiler.src', *map(str, arguments)], cwd=ROOT, text=True, capture_output=True)


def test_cli_checks_directories_without_executing_programs(tmp_path):
    (tmp_path / 'valid.zak').write_text('out("THIS MUST NOT EXECUTE")')
    result = command(tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'valid.zak: OK' in result.stdout
    assert 'THIS MUST NOT EXECUTE' not in result.stdout


def test_cli_returns_failure_and_checks_all_files(tmp_path):
    good = tmp_path / 'good.zak'
    bad = tmp_path / 'bad.zak'
    good.write_text('out(1)')
    bad.write_text('out(missing)')
    result = command(bad, good)
    assert result.returncode == 1
    assert f'{bad}:1:5: UNDEFINED_NAME:' in result.stdout
    assert f'{good}: OK' in result.stdout


def test_cli_json_and_io_errors(tmp_path):
    missing = tmp_path / 'missing.zak'
    result = command('--json', missing)
    assert result.returncode == 1
    entry, = json.loads(result.stdout)
    assert entry['path'] == str(missing)
    assert not entry['ok'] and entry['errors'][0]['code'] == 'IO_ERROR'


def test_cli_reports_empty_directory(tmp_path):
    result = command(tmp_path)
    assert result.returncode == 2 and 'No .zak files' in result.stderr
