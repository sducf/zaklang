"""Check every ZakBench task folder and prove its reference.py passes its hidden tests.

Usage, from the repository root:

    python3 zakbench/tasks/check_references.py

Each reference runs in a fresh, isolated, time-limited Python subprocess.
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
    if not (folder / 'reference.py').is_file():
        problems.append('reference.py is missing')
    return problems


def run_reference(folder):
    """Run reference.py against the hidden tests; return (passed, total, problem)."""
    task = json.loads((folder / 'task.json').read_text(encoding='utf-8'))
    cases_path = folder / 'hidden_tests.json'
    total = len(json.loads(cases_path.read_text(encoding='utf-8')))
    with tempfile.TemporaryDirectory() as workdir:
        try:
            result = subprocess.run(
                [sys.executable, '-I', '-c', CHILD,
                 str(folder / 'reference.py'), str(cases_path), task['functionName']],
                cwd=workdir, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return 0, total, f'timed out after {TIMEOUT_S}s'
    if result.returncode != 0:
        return 0, total, 'reference.py crashed or does not define the function'
    failed = json.loads(result.stdout)
    if failed:
        return total - len(failed), total, 'failed case ' + ', '.join(map(str, failed))
    return total, total, None


def main():
    folders = sorted(path for path in TASKS_DIR.iterdir() if path.is_dir() and not path.name.startswith(('.', '_')))
    passed_tasks = 0
    for folder in folders:
        problems = structure_problems(folder)
        if problems:
            print(f'{folder.name}: FAIL ' + '; '.join(problems))
            continue
        passed, total, problem = run_reference(folder)
        if problem:
            print(f'{folder.name}: FAIL {passed}/{total} {problem}')
            continue
        print(f'{folder.name}: PASS {passed}/{total}')
        passed_tasks += 1
    print(f'{len(folders)} tasks, {passed_tasks} passed')
    return 0 if folders and passed_tasks == len(folders) else 1


if __name__ == '__main__':
    sys.exit(main())
