"""Aggregate metrics for a matched Zak vs Python suite run (PRD F5).

summarize() is a pure function over stored run records, so a summary can be
recomputed from zakbench/results/<suite_run_id>/ without running inference again.
"""

from dataclasses import asdict, is_dataclass
from statistics import fmean, median

LANGUAGES = ('zak', 'python')
# Every run in one suite run must have the same values for these fields.
RUN_DEFINITION = ('suite', 'suite_run_id', 'model_id', 'spec_version', 'prompt_version', 'seed',
                  'temperature', 'max_tokens', 'max_attempts')


def summarize(runs):
    """Return the suite summary for a list of run records (dicts or RunResult-like dataclasses).

    Raises ValueError when the runs do not form complete Zak/Python pairs under one run definition.
    """
    runs = sorted((asdict(run) if is_dataclass(run) else run for run in runs),
                  key=lambda run: (run['task_id'], run['language']))
    if not runs:
        raise ValueError('there are no runs to summarize')
    definition = {field: runs[0].get(field) for field in RUN_DEFINITION}
    for run in runs:
        for field, value in definition.items():
            if run.get(field) != value:
                raise ValueError(f"{run['task_id']} {run['language']}: {field} is {run.get(field)!r}, "
                                 f'but other runs have {value!r}')

    pairs = {}
    for run in runs:
        pair = pairs.setdefault(run['task_id'], {})
        if run['language'] not in LANGUAGES or run['language'] in pair:
            raise ValueError(f"{run['task_id']}: unexpected or duplicate {run['language']!r} run")
        pair[run['language']] = run
    for task_id, pair in pairs.items():
        if len(pair) != 2:
            raise ValueError(f'{task_id}: needs one zak run and one python run')

    categories = sorted({run['category'] for run in runs})
    return {
        **definition,
        'overall': _group(pairs),
        'by_category': {
            category: _group({task_id: pair for task_id, pair in pairs.items()
                              if pair['zak']['category'] == category})
            for category in categories
        },
        'errors': [{'task_id': run['task_id'], 'language': run['language'], 'error': run.get('error')}
                   for run in runs if run['exec_outcome'] == 'error'],
    }


def _group(pairs):
    """Aggregate metrics for a set of tasks, each with one zak run and one python run."""
    languages = {language: _language([pair[language] for pair in pairs.values()]) for language in LANGUAGES}
    solved = {language: {task_id for task_id, pair in pairs.items() if pair[language]['passed']}
              for language in LANGUAGES}
    both = sorted(solved['zak'] & solved['python'])
    zak_tokens = [pairs[task_id]['zak']['total_tokens'] for task_id in both]
    python_tokens = [pairs[task_id]['python']['total_tokens'] for task_id in both]
    return {
        'tasks': len(pairs),
        'languages': languages,
        'correctness_gap': _round(languages['zak']['pass_at_k'] - languages['python']['pass_at_k']),
        'paired': {
            'tasks': both,
            'zak': _token_stats(zak_tokens),
            'python': _token_stats(python_tokens),
            'token_ratio': _ratio(sum(zak_tokens), sum(python_tokens)),
            'token_ratio_by_task': {task_id: _ratio(zak, python)
                                    for task_id, zak, python in zip(both, zak_tokens, python_tokens)},
        },
        'solved_by_zak_only': sorted(solved['zak'] - solved['python']),
        'solved_by_python_only': sorted(solved['python'] - solved['zak']),
        'solved_by_neither': sorted(set(pairs) - solved['zak'] - solved['python']),
    }


def _language(runs):
    # An error run has no attempts and counts as not passed.
    first_pass = sum(1 for run in runs if run['attempts'] and run['attempts'][0]['exec_outcome'] == 'pass')
    passed = sum(1 for run in runs if run['passed'])
    total_tokens = sum(run['total_tokens'] for run in runs)
    return {
        'runs': len(runs),
        'passed': passed,
        'errors': sum(1 for run in runs if run['exec_outcome'] == 'error'),
        'pass_at_1': _ratio(first_pass, len(runs)),
        'pass_at_k': _ratio(passed, len(runs)),
        'total_tokens': total_tokens,
        'repair_token_share': _ratio(sum(run['repair_tokens'] for run in runs), total_tokens),
    }


def _token_stats(tokens):
    if not tokens:
        return {'mean_total_tokens': None, 'median_total_tokens': None}
    return {'mean_total_tokens': _round(fmean(tokens)), 'median_total_tokens': _round(median(tokens))}


def _ratio(numerator, denominator):
    return _round(numerator / denominator) if denominator else None


def _round(value):
    # A fixed precision keeps summary.json readable and identical when recomputed.
    return round(value, 4)
