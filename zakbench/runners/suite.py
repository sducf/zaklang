"""Matched suite runs (PRD F5): every task in both languages under one run definition.

Each task gets one Zak run and one Python run with the same model, seed,
temperature, attempt limit, prompt version, and hidden tests. The two runs
share a pair_id. Results go to zakbench/results/<suite_run_id>/.
"""

import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import io
import json
from pathlib import Path

from zakbench.evaluation.summary import LANGUAGES, summarize
from zakbench.runners import run
from zakbench.runners.prompt import TASKS, load_task

SUITES = ('dev',)
CSV_COLUMNS = ('suite_run_id', 'pair_id', 'task_id', 'category', 'language', 'model_id', 'spec_version',
               'prompt_version', 'seed', 'temperature', 'max_tokens', 'max_attempts', 'exec_outcome',
               'passed', 'first_attempt_passed', 'attempts_used', 'prompt_tokens_total',
               'completion_tokens_total', 'total_tokens', 'first_attempt_tokens', 'repair_tokens',
               'latency_ms_total')


@dataclass
class SuiteResult:
    suite_run_id: str
    path: Path
    runs: list[dict]
    summary: dict


def suite_tasks(suite):
    """Return the task ids in a suite. The dev suite is every task folder."""
    if suite not in SUITES:
        raise ValueError(f'unknown suite: {suite}')
    return sorted(path.parent.name for path in TASKS.glob('*/task.json'))


def run_suite(suite, model_id, seed, prompt_version, spec_version, max_attempts=3, task_ids=None,
              results_dir=run.RESULTS):
    """Run every task in the suite once in Zak and once in Python, then write the summary.

    Raises ValueError for an unknown suite or task. A run that crashes is stored as an error run.
    """
    available = suite_tasks(suite)
    task_ids = available if task_ids is None else list(task_ids)
    for task_id in task_ids:
        if task_id not in available:
            raise ValueError(f'{task_id} is not in the {suite} suite')

    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    suite_run_id = f'{suite}-{stamp}'
    folder = Path(results_dir) / suite_run_id
    folder.mkdir(parents=True)

    runs = []
    for task_id in task_ids:
        category = load_task(task_id)['category']
        for language in LANGUAGES:
            record = _run_one(task_id, language, model_id, spec_version, prompt_version, seed, max_attempts)
            record.update(suite=suite, suite_run_id=suite_run_id, pair_id=f'{suite_run_id}:{task_id}',
                          category=category)
            # Write each run at once, so a stopped suite keeps the runs that finished.
            (folder / f'{task_id}-{language}.json').write_text(
                json.dumps(record, indent=2) + '\n', encoding='utf-8')
            runs.append(record)

    return SuiteResult(suite_run_id, folder, runs, write_summary(folder, runs))


def _run_one(task_id, language, model_id, spec_version, prompt_version, seed, max_attempts):
    try:
        return asdict(run.run_single(task_id, language, model_id, spec_version, prompt_version, seed,
                                     max_attempts))
    except Exception as error:  # One crashed run must not stop the other tasks.
        return {
            'task_id': task_id, 'language': language, 'model_id': model_id, 'spec_version': spec_version,
            'prompt_version': prompt_version, 'seed': seed, 'temperature': run.TEMPERATURE,
            'max_tokens': run.MAX_TOKENS, 'max_attempts': max_attempts, 'source_provided': False,
            'exec_outcome': 'error', 'compile_ok': None, 'tests_passed': 0, 'tests_total': 0,
            'passed': False, 'attempts_used': 0, 'prompt_tokens_total': 0, 'completion_tokens_total': 0,
            'total_tokens': 0, 'first_attempt_tokens': 0, 'repair_tokens': 0, 'latency_ms_total': 0,
            'attempts': [], 'error': f'{type(error).__name__}: {error}',
        }


def load_runs(folder):
    """Read every run JSON in a suite results folder."""
    paths = sorted(path for path in Path(folder).glob('*.json') if path.name != 'summary.json')
    if not paths:
        raise ValueError(f'no run results in {folder}')
    return [json.loads(path.read_text(encoding='utf-8')) for path in paths]


def write_summary(folder, runs):
    """Write summary.json and runs.csv for the runs and return the summary.

    The output depends only on the runs, so running it again gives the same bytes.
    """
    summary = summarize(runs)
    folder = Path(folder)
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')

    rows = io.StringIO()
    writer = csv.DictWriter(rows, CSV_COLUMNS, extrasaction='ignore', lineterminator='\n')
    writer.writeheader()
    for record in sorted(runs, key=lambda record: (record['task_id'], record['language'])):
        attempts = record['attempts']
        writer.writerow({**record, 'first_attempt_passed': bool(attempts) and
                         attempts[0]['exec_outcome'] == 'pass'})
    (folder / 'runs.csv').write_text(rows.getvalue(), encoding='utf-8')
    return summary
