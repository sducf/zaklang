"""Token savings by task size and Zak's break-even point (SD-60).

Zak pays a fixed cost for the spec and examples in every prompt and saves
tokens on each generated program. This reads the stored runs of one suite run
and, for every task both languages solved, compares Zak and Python total tokens
against task size. It is a pure function of the run records, like summary.py.

Task size is the completion tokens of the Python run's passing attempt: the
length of a working Python solution, counted by the reference model's own
tokenizer. It is read from the results, so no model server is needed.

Spec overhead is the Zak prompt minus the Python prompt on the first attempt,
which is the spec, the examples and their headings. Every attempt resends that
first message, so the overhead counts once per attempt. --spec-tokens replaces
it with a fixed count, for example the SD-54 measurement.
"""

import csv
import io
from statistics import fmean, linear_regression

from zakbench.evaluation.summary import summarize

CSV_COLUMNS = ('task_id', 'category', 'size_tokens', 'zak_tokens', 'python_tokens', 'zak_attempts',
               'spec_tokens', 'zak_minus_python', 'zak_minus_python_without_spec')
VARIANTS = {'zak_minus_python': 'Measured (spec included)',
            'zak_minus_python_without_spec': 'Spec subtracted'}
BINS = 4


def break_even_rows(runs, spec_tokens=None):
    """Return one row per task both languages solved, sorted by size, then task id.

    Raises ValueError when the runs are not one complete suite run (see summarize).
    """
    paired = summarize(runs)['overall']['paired']['tasks']
    by_task = {(run['task_id'], run['language']): run for run in runs}
    rows = []
    for task_id in paired:
        zak, python = by_task[task_id, 'zak'], by_task[task_id, 'python']
        overhead = spec_tokens
        if overhead is None:
            overhead = zak['attempts'][0]['prompt_tokens'] - python['attempts'][0]['prompt_tokens']
        measured = zak['total_tokens'] - python['total_tokens']
        rows.append({
            'task_id': task_id,
            'category': zak['category'],
            'size_tokens': python['attempts'][-1]['completion_tokens'],
            'zak_tokens': zak['total_tokens'],
            'python_tokens': python['total_tokens'],
            'zak_attempts': zak['attempts_used'],
            'spec_tokens': overhead,
            'zak_minus_python': measured,
            'zak_minus_python_without_spec': measured - overhead * zak['attempts_used'],
        })
    return sorted(rows, key=lambda row: (row['size_tokens'], row['task_id']))


def break_even(rows, variant):
    """Fit zak_minus_python = intercept + slope * size and say where, if anywhere, it crosses zero.

    The break-even size is reported only inside the suite's size range.
    """
    sizes = [row['size_tokens'] for row in rows]
    if len(set(sizes)) < 2:
        return {'intercept': None, 'slope': None, 'size': None,
                'statement': 'Not enough tasks of different sizes to fit a line.'}
    slope, intercept = linear_regression(sizes, [row[variant] for row in rows])
    low, high = min(sizes), max(sizes)
    fit = {'intercept': round(intercept, 2), 'slope': round(slope, 4), 'size': None}
    if slope and low <= -intercept / slope <= high:
        size = round(-intercept / slope)
        side = 'larger' if slope < 0 else 'smaller'
        return {**fit, 'size': size, 'statement': f'Zak breaks even at about {size} tokens of task size '
                                                  f'and uses fewer tokens on {side} tasks.'}
    cheaper = intercept + slope * low < 0
    return {**fit, 'statement': f"No break-even in the dev suite's size range ({low} to {high} tokens): "
                                f"Zak uses {'fewer' if cheaper else 'more'} tokens across all of it."}


def size_bins(rows, bins=BINS):
    """Split the size-sorted rows into up to `bins` groups of near-equal count, with mean differences."""
    count = min(bins, len(rows))
    groups = [rows[len(rows) * i // count:len(rows) * (i + 1) // count] for i in range(count)]
    return [{
        'low': group[0]['size_tokens'], 'high': group[-1]['size_tokens'], 'tasks': len(group),
        **{variant: round(fmean(row[variant] for row in group), 1) for variant in VARIANTS},
    } for group in groups]


def rows_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, CSV_COLUMNS, lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def report_markdown(rows):
    """The binned table and break-even statements, ready to paste into the baseline report."""
    lines = ['Task size: completion tokens of the passing Python attempt, on the reference model tokenizer.',
             'Values are Zak total tokens minus Python total tokens; negative means Zak used fewer.',
             f'Tasks both languages solved: {len(rows)}.', '']
    if not rows:
        return '\n'.join(lines + ['No task was solved by both languages, so there is nothing to compare.', ''])
    lines += ['| Task size (tokens) | Tasks | Measured (spec included) | Spec subtracted |',
              '|---|---|---|---|']
    lines += [f"| {b['low']} to {b['high']} | {b['tasks']} | {b['zak_minus_python']:g} | "
              f"{b['zak_minus_python_without_spec']:g} |" for b in size_bins(rows)]
    lines.append('')
    for variant, label in VARIANTS.items():
        result = break_even(rows, variant)
        lines.append(f"- {label}: {result['statement']}")
        if result['slope'] is not None:
            lines.append(f"  Fit: {result['intercept']} + {result['slope']} x size.")
    return '\n'.join(lines + [''])
