"""Print Zak failure tables and attempt evidence from a suite results folder.

Usage: python3 -m zakbench.reports.classify_failures <suite-results-folder>
"""

import argparse
import json
from collections import Counter
from pathlib import Path


SYNTAX_CODES = {'SYNTAX_ERROR', 'INVALID_LITERAL'}
TYPE_CODES = {'TYPE_MISMATCH', 'INVALID_TYPE', 'CANNOT_INFER_TYPE', 'VOID_VALUE'}
CRASH_CODES = {'INTERNAL_ERROR', 'IO_ERROR', 'PYTHON_AST_ERROR'}
CAUSES = ('Syntax', 'Type', 'Scope or semantics', 'Compiled but wrong answer',
          'Timeout or crash')


def classify(attempt, codes):
    """Prefer runtime failures, then the earliest compiler phase represented."""
    outcome = attempt['exec_outcome']
    if outcome in {'timeout', 'crash', 'oom'} or codes & CRASH_CODES:
        return 'Timeout or crash'
    if outcome == 'fail':
        return 'Compiled but wrong answer'
    if outcome != 'not_run':
        raise ValueError(f'unrecognized failed attempt outcome: {outcome}')
    # An empty generation reaches no compiler and has no diagnostic code.
    if codes & SYNTAX_CODES or (attempt['compile_ok'] is None and not attempt['code']):
        return 'Syntax'
    if codes & TYPE_CODES:
        return 'Type'
    return 'Scope or semantics'


def render(runs):
    runs = sorted((run for run in runs if run['language'] == 'zak'),
                  key=lambda run: run['task_id'])
    if not runs:
        raise ValueError('suite contains no Zak runs')
    causes = Counter()
    code_counts = Counter()
    followed_by_repair = Counter()
    compiled_on_repair = Counter()
    evidence = []

    for run in runs:
        attempts = sorted(run['attempts'], key=lambda attempt: attempt['number'])
        for index, attempt in enumerate(attempts):
            if attempt['exec_outcome'] == 'pass':
                continue
            diagnostics = attempt['compile_errors']
            codes = {diagnostic['code'] for diagnostic in diagnostics}
            cause = classify(attempt, codes)
            causes[cause] += 1
            code_counts.update(codes)
            if index + 1 < len(attempts):
                next_attempt = attempts[index + 1]
                if next_attempt['number'] != attempt['number'] + 1:
                    raise ValueError(f"missing attempt after {run['task_id']} #{attempt['number']}")
                followed_by_repair.update(codes)
                if next_attempt['compile_ok'] is True:
                    compiled_on_repair.update(codes)
            evidence.append((run['task_id'], attempt, cause))

    lines = [
        f'Analyzed {len(runs)} Zak runs and {len(evidence)} failed attempts.',
        '',
        '## Compiler diagnostics and next-attempt repair',
        '',
        'Each distinct code counts once per failed attempt. The rate uses attempts '
        'with a next repair as its denominator. A repair succeeds here if compilation '
        'succeeds, regardless of the test outcome.',
        '',
        '| Code | Failed attempts | Had a next repair | Next repair compiled | Rate |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for code, count in sorted(code_counts.items(), key=lambda item: (-item[1], item[0])):
        repairs = followed_by_repair[code]
        successes = compiled_on_repair[code]
        rate = f'{successes / repairs:.1%}' if repairs else 'N/A'
        lines.append(f'| {code} | {count} | {repairs} | {successes} | {rate} |')

    lines.extend([
        '', '## Failure causes', '',
        'Generations containing no code count under Syntax and have no compiler code. '
        'Runs with zero attempts contribute no failures.',
        '', '| Cause | Failed attempts |', '| --- | ---: |',
    ])
    lines.extend(f'| {cause} | {causes[cause]} |' for cause in CAUSES)
    lines.extend(['', '## Attempt evidence', ''])
    for task_id, attempt, cause in evidence:
        lines.append(f"- {task_id} #{attempt['number']} ({cause})")
        for diagnostic in attempt['compile_errors']:
            code = diagnostic['code']
            message = diagnostic.get('message', '')
            lines.append(f'  - {code} {message}'.rstrip())
            if code in SYNTAX_CODES and diagnostic.get('line'):
                source_lines = (attempt['code'] or '').splitlines()
                line = diagnostic['line']
                if 1 <= line <= len(source_lines):
                    lines.append(f'    - Source line {line} {source_lines[line - 1]!r}')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    try:
        paths = sorted(path for path in args.folder.glob('*.json') if path.name != 'summary.json')
        if not paths:
            raise ValueError(f'no run results in {args.folder}')
        report = render(json.loads(path.read_text(encoding='utf-8')) for path in paths)
    except (KeyError, OSError, ValueError) as error:
        parser.error(str(error))
    print(report)


if __name__ == '__main__':
    main()
