"""ZakBench command line. Run from the repository root with GPU_API_URL set:

    python3 -m zakbench run --task array_sum --lang zak
    python3 -m zakbench run --suite dev --lang both --model <id> --seed 0
    python3 -m zakbench run --suite dev --lang both --persist --user-email <email>   (also needs DATABASE_URL)
    python3 -m zakbench summarize zakbench/results/<suite_run_id>/
"""

import argparse
from pathlib import Path
import sys

from zakbench.runners.inference import InferenceError
from zakbench.runners.prompt import PROMPT_VERSION
from zakbench.runners.run import RESULTS, run_single, write_result
from zakbench.runners.suite import SUITES, load_runs, run_suite, write_summary


def open_store(user_email):
    """Connect to DATABASE_URL with the backend's own models and helpers."""
    backend = Path(__file__).resolve().parents[1] / 'backend'
    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))
    from sqlalchemy.exc import SQLAlchemyError
    from database.db import SessionLocal
    from api.controllers.suites import SuiteStore

    db = SessionLocal()
    try:
        return SuiteStore(db, user_email)
    except SQLAlchemyError as error:
        db.close()
        # Only the class name: the full message can contain the DATABASE_URL and its password.
        raise RuntimeError(f'could not reach the database ({type(error).__name__})') from None
    except Exception:
        db.close()
        raise


def main(argv=None, results_dir=RESULTS, open_store=open_store):
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
    run.add_argument('--persist', action='store_true',
                     help='also write the suite, its runs, and their attempts to the database in DATABASE_URL')
    run.add_argument('--user-email', help='with --persist: the existing user recorded as the one who launched it')
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

    if args.persist and not args.suite:
        parser.error('--persist needs --suite')
    if args.persist and not args.user_email:
        parser.error('--persist needs --user-email')

    if args.suite:
        if args.lang != 'both':
            parser.error('--suite needs --lang both')
        store = None
        try:
            # Open the store before any inference, so a bad DATABASE_URL or email stops the suite early.
            store = open_store(args.user_email) if args.persist else None
            result = run_suite(args.suite, args.model, args.seed, args.prompt_version, args.spec_version,
                               args.max_attempts, results_dir=results_dir, store=store)
        except (ValueError, RuntimeError) as error:
            print(f'error: {error}', file=sys.stderr)
            return 1
        finally:
            if store:
                store.db.close()
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
