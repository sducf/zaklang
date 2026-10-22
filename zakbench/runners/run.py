"""Single-run repair loop (PRD F5): generate, compile, evaluate, and feed failures back.

Zak is compiled and transpiled, and Python is syntax-checked, inside evaluate()
before anything runs in the sandbox.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

from zakbench.evaluation.evaluator import EvalResult, evaluate
from zakbench.evaluation.metrics import Attempt, compute_run_metrics
from zakbench.runners.inference import generate
from zakbench.runners.prompt import PROMPT_VERSION, build_prompt, extract_code, load_task, repair_prompt

TEMPERATURE = 0.0
MAX_TOKENS = 1024
RESULTS = Path(__file__).resolve().parents[1] / 'results'


@dataclass
class RunResult:
    # Run definition
    task_id: str
    language: str
    model_id: str
    spec_version: str | None
    prompt_version: str
    seed: int
    temperature: float
    max_tokens: int
    max_attempts: int
    source_provided: bool
    # Outcome of the last attempt
    exec_outcome: str
    compile_ok: bool | None
    tests_passed: int
    tests_total: int
    # PRD F5 run metrics over every attempt
    passed: bool
    attempts_used: int
    prompt_tokens_total: int
    completion_tokens_total: int
    total_tokens: int
    first_attempt_tokens: int
    repair_tokens: int
    latency_ms_total: int
    attempts: list[dict]


def run_single(task_id, language, model_id, spec_version, prompt_version, seed, max_attempts=3, source=None):
    """Run one task in one language for up to max_attempts and return the result.

    When source is given, attempt 1 evaluates it instead of generating, and no repairs run.
    Raises ValueError for bad arguments, InferenceError when the model server fails,
    and RuntimeError when Docker is unavailable.
    """
    if prompt_version != PROMPT_VERSION:
        raise ValueError(f'unknown prompt version: {prompt_version}')
    if max_attempts < 1:
        raise ValueError('max_attempts must be at least 1')
    task = load_task(task_id)
    messages = [{'role': 'user', 'content': build_prompt(task, language, spec_version)}]

    attempts = []
    for number in range(1, max_attempts + 1):
        if source is not None:
            completion, code = None, source
            prompt_tokens = completion_tokens = latency_ms = 0
            finish_reason = None
        else:
            generation = generate(messages, seed=seed, max_tokens=MAX_TOKENS, temperature=TEMPERATURE)
            completion, code = generation.text, extract_code(generation.text)
            prompt_tokens, completion_tokens = generation.prompt_tokens, generation.completion_tokens
            latency_ms, finish_reason = generation.latency_ms, generation.finish_reason

        if code:
            evaluation = evaluate(code, task_id, language)
        else:
            evaluation = EvalResult('not_run', 0, 0, [], 'The response contained no code.', None)

        attempts.append({
            'number': number,
            'prompt': None if source is not None else messages,
            'completion': completion,
            'code': code,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'latency_ms': latency_ms,
            'finish_reason': finish_reason,
            'compile_ok': evaluation.compile_ok,
            'compile_errors': evaluation.compile_errors,
            'transpiled_python': evaluation.transpiled_python,
            'exec_outcome': evaluation.exec_outcome,
            'tests_passed': evaluation.tests_passed,
            'tests_total': evaluation.tests_total,
            'failure_summary': evaluation.failure_summary,
        })
        if evaluation.exec_outcome == 'pass' or source is not None:
            break
        messages = [*messages, {'role': 'assistant', 'content': completion},
                    {'role': 'user', 'content': repair_prompt(language, evaluation.failure_summary)}]

    metrics = compute_run_metrics([
        Attempt(a['prompt_tokens'], a['completion_tokens'], a['latency_ms'], a['exec_outcome'] == 'pass')
        for a in attempts])
    last = attempts[-1]
    return RunResult(
        task_id=task_id, language=language, model_id=model_id, spec_version=spec_version,
        prompt_version=prompt_version, seed=seed, temperature=TEMPERATURE, max_tokens=MAX_TOKENS,
        max_attempts=max_attempts, source_provided=source is not None,
        exec_outcome=last['exec_outcome'], compile_ok=last['compile_ok'],
        tests_passed=last['tests_passed'], tests_total=last['tests_total'],
        **asdict(metrics), attempts=attempts)


def write_result(result, results_dir=RESULTS):
    """Write the result as JSON to results_dir and return the file path."""
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    path = Path(results_dir) / f'{result.task_id}-{result.language}-{stamp}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(result), indent=2) + '\n', encoding='utf-8')
    return path
