# SD-38: llama-server inference client

## Outcome and branch

Build the Python client that SD-36's runner uses to ask the model for code
and get exact token counts back. Branch `SD-38-llama-server-inference-client`
from `main` at `7fc6c5d`. No dependencies: llama-server (SD-18) and the
Tailscale route (SD-20) are done, and the backend already reaches the server
through `GPU_API_URL` (`backend/api/controllers/testing.py`).

## Current state

- Nothing in ZakBench calls the model. `zakbench/runners/` holds only a README.
- `GPU_API_URL` is the only GPU setting in `backend/.env.example`. The health
  check calls `{GPU_API_URL}/health` with no API key.
- `spec/count_tokens.py` already calls the server's `/tokenize`; nothing calls
  chat completions.

## Interface

`zakbench/runners/inference.py`:

```python
class InferenceError(Exception): ...          # unreachable, HTTP error, bad response
class InferenceTimeout(InferenceError): ...   # request took longer than timeout_s

@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model_id: str
    finish_reason: str | None

def generate(
    messages: list[dict[str, str]],
    *,
    seed: int,
    max_tokens: int,
    temperature: float = 0.0,
    timeout_s: float = 120.0,
) -> Generation: ...
```

The ticket's interface plus two small additions:
- `finish_reason`, because `attempts.finish_reason` already exists in the
  schema and `"length"` tells the runner the completion was cut off.
- `timeout_s`, because the ticket requires a typed timeout error, so the
  timeout has to be set somewhere.

## Behavior

- `POST {GPU_API_URL}/v1/chat/completions` with `messages`, `seed`,
  `temperature`, `max_tokens`, and `cache_prompt: false`.
  - llama.cpp documents that reusing the prompt cache can change results
    slightly. Turning it off keeps repeated runs identical.
- The URL is read from the environment on every call, not at import. Tests
  and the backend can then set it without reloading the module. A missing
  URL raises `InferenceError`.
- `text` comes from `choices[0].message.content`. `prompt_tokens` and
  `completion_tokens` come from `usage`, exactly as returned. A missing or
  non-integer usage field raises `InferenceError`; token counts are never
  estimated.
- `model_id` comes from the response's `model` field. `latency_ms` is
  wall-clock time around the HTTP call.
- Errors:
  - A timeout raises `InferenceTimeout`.
  - Connection failures, non-2xx status codes and malformed JSON raise
    `InferenceError` with a short message.
  - Messages include the status code but never the request body, so prompts
    don't end up in logs.
- Uses stdlib `urllib.request` only. ZakBench gets no new dependency, and the
  backend can import it as is.

## Determinism check (manual AC)

`python -m zakbench.runners.inference "Write a function that adds two numbers."`
sends the same single-message prompt twice with `seed=0` and prints both
results and whether text and token counts match. Run it with `GPU_API_URL` set
and paste the output in the PR.

## Tests (`zakbench/tests/test_inference.py`, unittest)

A stdlib `http.server` on `127.0.0.1:0` in a background thread stands in for
llama-server.

1. Success: the request body carries the messages, seed, temperature,
   max_tokens and `cache_prompt: false`, and usage values pass through
   unchanged.
2. Multi-turn `messages` are sent in order.
3. An HTTP 500 raises `InferenceError` (not `InferenceTimeout`) and the
   message has the status code.
4. A slow server with `timeout_s=0.2` raises `InferenceTimeout`.
5. A closed port raises `InferenceError`.
6. A response without `usage` raises `InferenceError`.
7. An unset `GPU_API_URL` raises `InferenceError`.

Run: `python -m unittest discover -s zakbench/tests -t .`

## Files

- Create `zakbench/__init__.py`, `zakbench/runners/__init__.py`,
  `zakbench/tests/__init__.py` (empty; SD-39 adds the same empty files).
- Create `zakbench/runners/inference.py` and `zakbench/tests/test_inference.py`.
- Update `zakbench/runners/README.md` with usage.

## Out of scope

Streaming, model registry, retries, API keys, async client. Add them only when
a ticket needs them.
