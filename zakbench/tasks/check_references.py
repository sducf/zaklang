"""Check every ZakBench task folder and prove its references pass its hidden tests.

Usage, from the repository root, with compiler/requirements.txt installed:

    python3 zakbench/tasks/check_references.py

reference.py runs as is. reference.zak is compiled and transpiled to Python
first. Each reference runs in a fresh, isolated, time-limited Python subprocess.
Failures report only the task and case number, never hidden-test values,
so the hidden tests do not end up in logs.

Exit code 0 means every task passed every check; 1 means at least one failed.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

TASKS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TASKS_DIR.parents[1]))

from compiler.src import TranspileError, compile as compile_zak, transpile  # noqa: E402

TIMEOUT_S = 5
MIN_CASES = 5
MAX_CASES = 12
TASK_FIELDS = {'id', 'title', 'category', 'prompt', 'functionName', 'inputs', 'outputType'}

# Runs in the child process. Prints the indices of failing cases, never their values.
CHILD = '''import json
import runpy
import sys

solution = runpy.run_path(sys.argv[1])[sys.argv[3]]
with open(sys.argv[2], encoding="utf-8") as handle:
    cases = json.load(handle)
failed = []
for index, case in enumerate(cases, start=1):
    try:
        if solution(*case["inputs"]) != case["expected"]:
            failed.append(index)
    except Exception:
        failed.append(index)
print(json.dumps(failed))
'''


def structure_problems(folder):
    """Return a list of problems with the folder's files, or an empty list."""
    problems = []
    try:
        task = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        return [f'task.json does not load: {type(error).__name__}']
    try:
        cases = json.loads((folder / 'hidden_tests.json').read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        return [f'hidden_tests.json does not load: {type(error).__name__}']

    missing = TASK_FIELDS - task.keys()
    if missing:
        problems.append(f'task.json is missing {", ".join(sorted(missing))}')
    if task.get('id') != folder.name:
        problems.append('task.json id does not match the folder name')
    if not isinstance(cases, list) or not MIN_CASES <= len(cases) <= MAX_CASES:
        problems.append(f'hidden_tests.json must hold {MIN_CASES} to {MAX_CASES} cases')
    else:
        arity = len(task.get('inputs', []))
        for index, case in enumerate(cases, start=1):
            if set(case) != {'inputs', 'expected'} or len(case['inputs']) != arity:
                problems.append(f'case {index} does not match the task inputs')
    for name in ('reference.py', 'reference.zak'):
        if not (folder / name).is_file():
            problems.append(f'{name} is missing')
    return problems


def run_solution(folder, name, source):
    """Run Python source against the hidden tests; return (passed, total, problem)."""
    task = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
    cases_path = folder / 'hidden_tests.json'
    total = len(json.loads(cases_path.read_text(encoding='utf-8')))
    with tempfile.TemporaryDirectory() as workdir:
        solution_path = Path(workdir) / 'solution.py'
        solution_path.write_text(source, encoding='utf-8')
        try:
            result = subprocess.run(
                [sys.executable, '-I', '-c', CHILD,
                 str(solution_path), str(cases_path), task['functionName']],
                cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return 0, total, f'{name} timed out after {TIMEOUT_S}s'
    if result.returncode != 0:
        return 0, total, f'{name} crashed or does not define the function'
    failed = json.loads(result.stdout)
    if failed:
        return total - len(failed), total, f'{name} failed case ' + ', '.join(map(str, failed))
    return total, total, None


def run_reference(folder):
    """Run reference.py against the hidden tests; return (passed, total, problem)."""
    return run_solution(folder, 'reference.py', (folder / 'reference.py').read_text(encoding='utf-8'))


def describe(error):
    """Format a compiler error the same way the compiler CLI does."""
    return f'{error.line}:{error.col}: {error.code}: {error.message}'


def run_zak_reference(folder):
    """Compile, transpile and run reference.zak against the hidden tests; return (passed, total, problem)."""
    total = len(json.loads((folder / 'hidden_tests.json').read_text(encoding='utf-8')))
    result = compile_zak((folder / 'reference.zak').read_text(encoding='utf-8'))
    if not result.ok or result.ast is None:
        return 0, total, 'reference.zak does not compile: ' + describe(result.errors[0])
    try:
        source = transpile(result.ast)
    except TranspileError as error:
        return 0, total, 'reference.zak does not transpile: ' + describe(error.errors[0])
    return run_solution(folder, 'reference.zak', source)


def check_task(folder):
    """Check one task folder; return (ok, report line)."""
    problems = structure_problems(folder)
    if problems:
        return False, f'{folder.name}: FAIL ' + '; '.join(problems)
    counts = []
    failures = []
    for label, run in (('py', run_reference), ('zak', run_zak_reference)):
        passed, total, problem = run(folder)
        counts.append(f'{label} {passed}/{total}')
        if problem:
            failures.append(problem)
    if failures:
        return False, f'{folder.name}: FAIL ' + ', '.join(counts) + ' ' + '; '.join(failures)
    return True, f'{folder.name}: PASS ' + ', '.join(counts)


def main():
    folders = sorted(path for path in TASKS_DIR.iterdir() if path.is_dir() and not path.name.startswith(('.', '_')))
    passed_tasks = 0
    for folder in folders:
        ok, line = check_task(folder)
        print(line)
        passed_tasks += ok
    print(f'{len(folders)} tasks, {passed_tasks} passed')
    return 0 if folders and passed_tasks == len(folders) else 1


if __name__ == '__main__':
    sys.exit(main())
