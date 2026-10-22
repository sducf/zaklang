# runners/

Code that drives a benchmark run.

A runner will eventually be responsible for loading a task from `tasks/`,
filling in a template from `prompts/`, sending it to the model, and executing
the generated solution.

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

Tests use a local fake server and need no GPU:

```sh
python3 -m unittest discover -s zakbench/tests -t .
```

To check determinism against the real server, send the same prompt twice and
compare. The command exits 0 and prints `identical: true` when the text and
token counts match:

```sh
GPU_API_URL=<server url> python3 -m zakbench.runners.inference "Write a Python function that adds two numbers."
```
