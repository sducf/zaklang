"""ZakBench command line. Run from the repository root with GPU_API_URL set:

    python3 -m zakbench run --task array_sum --lang zak
    python3 -m zakbench run --suite dev --lang both --model <id> --seed 0
    python3 -m zakbench summarize zakbench/results/<suite_run_id>/
"""

import argparse
import sys

from zakbench.runners.inference import InferenceError
from zakbench.runners.prompt import PROMPT_VERSION
from zakbench.runners.run import RESULTS, run_single, write_result
from zakbench.runners.suite import SUITES, load_runs, run_suite, write_summary


def main(argv=None, results_dir=RESULTS):
    parser = argparse.ArgumentParser(prog='zakbench')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='run one task in one language, or a suite in both languages')
    target = run.add_mutually_exclusive_group(required=True)
    target.add_argument('--task')
    target.add_argument('--suite', choices=SUITES)
    run.add_argument('--lang', choices=['zak', 'python', 'both'], required=True)
    run.add_argument('--model', default='llama-3.1-8b', help='model id recorded in the result')
    run.add_argument('--seed', type=int, default=0)
    run.add_argument('--spec-version', default='0.1')
    run.add_argument('--prompt-version', default=PROMPT_VERSION)
    run.add_argument('--max-attempts', type=int, default=3)
    summarize = commands.add_parser('summarize', help='write summary.json and runs.csv for a suite run')
    summarize.add_argument('folder')
    args = parser.parse_args(argv)

    if args.command == 'summarize':
        try:
            summary = write_summary(args.folder, load_runs(args.folder))
        except (OSError, ValueError, KeyError) as error:
            print(f'error: {error}', file=sys.stderr)
            return 1
        _print_summary(summary)
        return 0

    if args.suite:
        if args.lang != 'both':
            parser.error('--suite needs --lang both')
        try:
            result = run_suite(args.suite, args.model, args.seed, args.prompt_version, args.spec_version,
                               args.max_attempts, results_dir=results_dir)
        except ValueError as error:
            print(f'error: {error}', file=sys.stderr)
            return 1
        _print_summary(result.summary)
        print(result.path)
        return 0

    if args.lang == 'both':
        parser.error('--lang both needs --suite')
    try:
        result = run_single(args.task, args.lang, args.model, args.spec_version, args.prompt_version,
                            args.seed, args.max_attempts)
    except (InferenceError, RuntimeError, ValueError) as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    path = write_result(result, results_dir)
    print(f'{result.task_id} {result.language}: {result.exec_outcome} after {result.attempts_used} '
          f'attempt(s), {result.total_tokens} tokens')
    print(path)
    return 0


def _print_summary(summary):
    overall = summary['overall']
    for language, stats in overall['languages'].items():
        print(f"{language}: pass@1 {stats['pass_at_1']}, pass@k {stats['pass_at_k']}, "
              f"{stats['errors']} error(s)")
    paired = overall['paired']
    print(f"paired tasks: {len(paired['tasks'])} of {overall['tasks']}, "
          f"zak/python token ratio {paired['token_ratio']}")


if __name__ == '__main__':
    sys.exit(main())
