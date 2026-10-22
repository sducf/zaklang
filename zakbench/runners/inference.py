"""Client for the llama-server that generates benchmark code.

Token counts come from the server's own usage data, never estimates, because
tokens-to-correctness is the benchmark's core metric.

Determinism check, from the repository root with GPU_API_URL set:

    python3 -m zakbench.runners.inference "Write a Python function that adds two numbers."
"""

from dataclasses import asdict, dataclass
import json
import os
import sys
import time
import urllib.error
import urllib.request


class InferenceError(Exception):
    """The server could not be reached, returned an error, or sent an unusable response."""


class InferenceTimeout(InferenceError):
    """The server did not answer within the timeout."""


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model_id: str
    finish_reason: str | None


def generate(messages, *, seed, max_tokens, temperature=0.0, timeout_s=120.0):
    """Send chat messages to llama-server and return its completion with exact token counts."""
    base_url = os.getenv('GPU_API_URL', '').rstrip('/')
    if not base_url:
        raise InferenceError('GPU_API_URL is not set')
    body = {
        'messages': messages,
        'seed': seed,
        'temperature': temperature,
        'max_tokens': max_tokens,
        # A reused prompt cache can change results slightly, so repeated runs would not match.
        'cache_prompt': False,
    }
    request = urllib.request.Request(
        f'{base_url}/v1/chat/completions', data=json.dumps(body).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            reply = json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise InferenceError(f'llama-server returned HTTP {error.code}') from None
    except TimeoutError:
        raise InferenceTimeout(f'llama-server did not answer within {timeout_s:g}s') from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise InferenceTimeout(f'llama-server did not answer within {timeout_s:g}s') from None
        raise InferenceError(f'could not reach llama-server: {error.reason}') from None
    except (OSError, ValueError) as error:
        raise InferenceError(f'bad response from llama-server: {type(error).__name__}') from None
    latency_ms = round((time.monotonic() - started) * 1000)

    try:
        choice = reply['choices'][0]
        text = choice['message']['content']
        prompt_tokens = reply['usage']['prompt_tokens']
        completion_tokens = reply['usage']['completion_tokens']
    except (KeyError, IndexError, TypeError):
        raise InferenceError('llama-server response is missing the completion or token usage') from None
    if not isinstance(text, str) or type(prompt_tokens) is not int or type(completion_tokens) is not int:
        raise InferenceError('llama-server response has invalid completion or token usage')

    return Generation(text, prompt_tokens, completion_tokens, latency_ms,
                      str(reply.get('model', '')), choice.get('finish_reason'))


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    messages = [{'role': 'user', 'content': argv[1]}]
    try:
        first, second = (generate(messages, seed=0, max_tokens=256) for _ in range(2))
    except InferenceError as error:
        print(f'error: {error}', file=sys.stderr)
        return 1
    for label, result in (('first', first), ('second', second)):
        print(label, json.dumps(asdict(result), indent=2))
    identical = (first.text, first.prompt_tokens, first.completion_tokens) == \
        (second.text, second.prompt_tokens, second.completion_tokens)
    print('identical:', str(identical).lower())
    return 0 if identical else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
