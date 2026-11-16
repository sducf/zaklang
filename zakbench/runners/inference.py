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


# Seconds to wait before each retry of a transient failure: 2 retries, so 3 tries in all.
RETRY_DELAYS_S = (2, 4)


class InferenceError(Exception):
    """The server could not be reached, returned an error, or sent an unusable response.

    transient is True for failures worth retrying: a timeout, an HTTP 5xx, or a dropped connection.
    """

    def __init__(self, message, transient=False):
        super().__init__(message)
        self.transient = transient


class InferenceTimeout(InferenceError):
    """The server did not answer within the timeout."""

    def __init__(self, message):
        super().__init__(message, transient=True)


@dataclass(frozen=True)
class Generation:
    text: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    model_id: str
    finish_reason: str | None
    retries: int = 0


def generate(messages, *, seed, max_tokens, temperature=0.0, timeout_s=120.0):
    """Send chat messages to llama-server and return its completion with exact token counts.

    A transient failure is retried after each delay in RETRY_DELAYS_S. Requests are deterministic,
    so a retry gets the same completion. Tokens and latency come from the successful try only.
    """
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

    for retries, delay in enumerate((*RETRY_DELAYS_S, None)):
        started = time.monotonic()
        try:
            reply = _post(request, timeout_s)
            break
        except InferenceError as error:
            if not error.transient or delay is None:
                raise
            time.sleep(delay)
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
                      str(reply.get('model', '')), choice.get('finish_reason'), retries)


def _post(request, timeout_s):
    """Send one request and return the parsed reply. Raises InferenceError, marked transient or not."""
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        raise InferenceError(f'llama-server returned HTTP {error.code}', transient=error.code >= 500) from None
    except TimeoutError:
        raise InferenceTimeout(f'llama-server did not answer within {timeout_s:g}s') from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise InferenceTimeout(f'llama-server did not answer within {timeout_s:g}s') from None
        raise InferenceError(f'could not reach llama-server: {error.reason}', transient=True) from None
    except (OSError, ValueError) as error:
        # A connection dropped mid-response is worth retrying. Bad JSON is not.
        raise InferenceError(f'bad response from llama-server: {type(error).__name__}',
                             transient=isinstance(error, ConnectionError)) from None


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
