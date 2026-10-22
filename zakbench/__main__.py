"""ZakBench command line. Run from the repository root with GPU_API_URL set:

    python3 -m zakbench run --task array_sum --lang zak
"""

import argparse
import sys

from zakbench.runners.inference import InferenceError
from zakbench.runners.prompt import PROMPT_VERSION
from zakbench.runners.run import RESULTS, run_single, write_result


def main(argv=None, results_dir=RESULTS):
    parser = argparse.ArgumentParser(prog='zakbench')
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='run one task in one language and write a JSON result')
    run.add_argument('--task', required=True)
    run.add_argument('--lang', choices=['zak', 'python'], required=True)
    run.add_argument('--model', default='llama-3.1-8b', help='model id recorded in the result')
    run.add_argument('--seed', type=int, default=0)
    run.add_argument('--spec-version', default='0.1')
    run.add_argument('--prompt-version', default=PROMPT_VERSION)
    run.add_argument('--max-attempts', type=int, default=3)
    args = parser.parse_args(argv)

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


if __name__ == '__main__':
    sys.exit(main())
