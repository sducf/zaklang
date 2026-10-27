# runners/

Code that drives a benchmark run.

A run loads a task from `tasks/`, fills in a template from `prompts/`, sends
it to the model, and checks the generated solution against the hidden tests,
feeding failures back for repair.

## Running one task

From the repository root, with `compiler/requirements.txt` installed, the
`zaklang-sandbox` Docker image built, and `GPU_API_URL` set:

```sh
python3 -m zakbench run --task array_sum --lang zak
python3 -m zakbench run --task array_sum --lang python --model <id> --seed 0
```

It prints the outcome and writes the full result as JSON to `zakbench/results/`.
The defaults are `--model llama-3.1-8b` (a label recorded in the result),
`--seed 0`, `--spec-version 0.1`, `--prompt-version 1`, and `--max-attempts 3`.

## Running a suite in both languages

```sh
python3 -m zakbench run --suite dev --lang both --model <id> --seed 0
python3 -m zakbench summarize zakbench/results/<suite_run_id>/
```

`run --suite` runs every task in the dev suite once in Zak and once in Python,
with the same model, seed, temperature, attempt limit, spec version, and
prompt version. It writes to `zakbench/results/<suite_run_id>/`:

- `<task_id>-<language>.json`: one `RunResult` per run, plus `suite`,
  `suite_run_id`, `category`, and a `pair_id` that the two runs of a task share.
- `summary.json`: the aggregate metrics from `evaluation/summary.py`.
- `runs.csv`: one row per run with the run definition, outcome, attempts, and
  token columns.

Each run file is written when its run ends, so a stopped suite keeps the runs
that finished. A run that crashes the harness, for example when the model
server is down, is stored as an `error` run, and the suite continues.

`summarize` reads the run files in a folder and writes `summary.json` and
`runs.csv` again. The output depends only on the run files, so it is the same
byte for byte.

## suite.py

`run_suite(suite, model_id, seed, prompt_version, spec_version,
max_attempts=3, task_ids=None)` runs the suite and returns a `SuiteResult`
with the `suite_run_id`, the folder, the run records, and the summary. Pass
`task_ids` to run only some tasks. The dev suite is every folder in
`zakbench/tasks/` that has a `task.json`.

## run.py

`run_single(task_id, language, model_id, spec_version, prompt_version, seed,
max_attempts=3, source=None)` runs the PRD F5 attempt loop and returns a
`RunResult`:

1. Generate with temperature 0, the given seed, and at most 1024 tokens.
2. Evaluate with `evaluate()` from `evaluation/`. It compiles and transpiles
   Zak, syntax-checks Python, and runs the code against the hidden tests in
   the sandbox.
3. On failure, append the model's answer and a repair message holding the
   compile errors or SD-39's bounded failure summary, then go back to step 1.
   Stop on pass or after `max_attempts`.

Each attempt stores the chat messages sent, the raw completion, the extracted
code, prompt and completion tokens, latency, `compile_ok`, `compile_errors`,
`transpiled_python`, `exec_outcome`, and the failure summary. Token totals
cover every attempt, including repairs. When `source` is given (Playground
code), attempt 1 evaluates it instead of generating, and no repairs run.

## prompt.py

`build_prompt(task, language, spec_version)` fills `zak_prompt.txt` or
`python_prompt.txt` from `task.json` only, so hidden tests never reach the
model. Both languages get the same task fields. The Zak prompt also gets the
`zak_spec` and `zak_examples` sections of `spec/zak-core-v<spec_version>.md`.
`PROMPT_VERSION` is `"1"` and must be bumped when the templates change.

If the model wraps its answer in a Markdown code fence, the first fenced block
is used as the code.

## inference.py

Client for the llama-server on the GPU host (SD-38). It reads the server URL
from `GPU_API_URL`, the same variable the backend uses.

```python
from zakbench.runners.inference import generate

result = generate(
    [{'role': 'user', 'content': prompt}],
    seed=0,
    max_tokens=512,
)
result.text, result.prompt_tokens, result.completion_tokens, result.latency_ms
```

- `messages` is a list of chat messages, so the repair loop can append the
  model's answer and the error feedback and call again.
- Benchmark defaults are temperature 0 and a fixed seed. The prompt cache is
  turned off so repeated runs give identical results.
- `prompt_tokens` and `completion_tokens` are copied from the server's usage
  data. A response without them raises an error instead of being estimated.
- `finish_reason` is `"length"` when `max_tokens` cut the completion off.
- `InferenceTimeout` is raised when the server takes longer than `timeout_s`
  (default 120 s). `InferenceError` covers every other failure: no URL,
  unreachable server, HTTP error, or bad response. Error messages never
  include the prompt.

Tests fake the model server and Docker, so they need no GPU or image:

```sh
python3 -m unittest discover -s zakbench/tests -t .
```

To check determinism against the real server, send the same prompt twice and
compare. The command exits 0 and prints `identical: true` when the text and
token counts match:

```sh
GPU_API_URL=<server url> python3 -m zakbench.runners.inference "Write a Python function that adds two numbers."
```
