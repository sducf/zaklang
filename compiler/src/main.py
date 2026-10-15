"""Static compiler API and command-line diagnostics. Zak code is never executed."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from lark import UnexpectedInput, VisitError

from .errors import CompileError, CompileResult
from .parser import parse
from .semantic import check


def _failure(code: str, message: str, line: int = 1, col: int = 1) -> CompileResult:
    """Create an unsuccessful result with coordinates clamped to one-based values."""
    return CompileResult(False, None, [CompileError(max(1, line), max(1, col), code, message)])


def compile(source: str) -> CompileResult:
    """Return a checked AST or located diagnostics; never execute the source.

    Ordinary compilation failures are values. Process-control exceptions such
    as KeyboardInterrupt and SystemExit propagate to the caller.
    """
    try:
        program = parse(source)
        errors = check(program)
        return CompileResult(not errors, None if errors else program, errors)
    except UnexpectedInput as error:
        token = getattr(error, 'token', None)

        if token is not None and token.type == '$END':
            line = source.count('\n') + 1
            col = len(source.rsplit('\n', 1)[-1]) + 1
        
            return _failure('SYNTAX_ERROR', 'Unexpected end of source.', line, col)
        
        return _failure('SYNTAX_ERROR', 'Unexpected input; check syntax and statement separators.', error.line, error.column)
    except VisitError as error:
        if isinstance(error.orig_exc, RecursionError):
            return _failure('COMPLEXITY_LIMIT', 'Source nesting exceeds the compiler limit.')
        
        if isinstance(error.orig_exc, (ValueError, OverflowError)):
            meta = getattr(error.obj, 'meta', error.obj)
            return _failure('INVALID_LITERAL', 'Invalid string or numeric literal.', getattr(meta, 'line', 1), getattr(meta, 'column', 1))
        
        return _failure('INTERNAL_ERROR', 'An internal compiler error prevented analysis.')
    except RecursionError:
        return _failure('COMPLEXITY_LIMIT', 'Source nesting exceeds the compiler limit.')
    except Exception:
        return _failure('INTERNAL_ERROR', 'An internal compiler error prevented analysis.')

def main(argv: list[str] | None = None) -> int:
    """Check paths recursively, print diagnostics, and return a shell exit code."""
    
    parser = argparse.ArgumentParser(description='Statically check Zak files without executing them.')
    parser.add_argument('paths', nargs='+', type=Path, help='.zak files or directories to check recursively')
    parser.add_argument('--json', action='store_true', help='emit machine-readable diagnostic results')
    
    arguments = parser.parse_args(argv)
    files: list[Path] = []
    
    for path in arguments.paths:
        files.extend(sorted(path.rglob('*.zak')) if path.is_dir() else [path])
    
    files = list(dict.fromkeys(files))
    
    if not files:
        parser.error('No .zak files found in the supplied directories.')
    
    results = []
    
    for path in files:
        try:
            result = compile(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError) as error:
            result = _failure('IO_ERROR', f'Cannot read source: {error}')
    
        results.append({'path': str(path), 'ok': result.ok, 'errors': [asdict(error) for error in result.errors]})
    
        if not arguments.json:
            if result.ok:
                print(f'{path}: OK')
            for error in result.errors:
                print(f'{path}:{error.line}:{error.col}: {error.code}: {error.message}')

    # Write the compiler results in a json file so we know if everything went ok, and if any errors happened
    if arguments.json:
        print(json.dumps(results, ensure_ascii=True))
    
    return 0 if all(result['ok'] for result in results) else 1


if __name__ == '__main__':
    sys.exit(main())
