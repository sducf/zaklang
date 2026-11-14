"""Tests for the inference client. Run from the repository root:
python3 -m unittest discover -s zakbench/tests -t .
"""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import threading
import time
import unittest
import urllib.error
from unittest.mock import patch

from zakbench.runners import inference
from zakbench.runners.inference import Generation, InferenceError, InferenceTimeout, generate

MESSAGES = [{'role': 'user', 'content': 'Write solve(a, b) that returns a + b.'}]
REPLY = {
    'model': 'llama-3.1-8b-instruct-q4km',
    'choices': [{'message': {'role': 'assistant', 'content': 'def solve(a, b):\n    return a + b\n'},
                 'finish_reason': 'stop'}],
    'usage': {'prompt_tokens': 31, 'completion_tokens': 17, 'total_tokens': 48},
}


class FakeServer:
    """llama-server stand-in that records requests and answers with a fixed status, body and delay.

    status can be a list: request n gets status[n], and the last one repeats.
    """

    def __init__(self, status=200, body=REPLY, delay_s=0.0):
        statuses = status if isinstance(status, list) else [status]
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['Content-Length'])
                fake.requests.append((self.path, json.loads(self.rfile.read(length))))
                code = statuses[min(len(fake.requests), len(statuses)) - 1]
                time.sleep(delay_s)
                payload = json.dumps(body if code == 200 else {'error': 'boom'}).encode()
                try:
                    self.send_response(code)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except OSError:
                    pass  # The client gave up after its timeout.

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.url = f'http://127.0.0.1:{self.server.server_port}'
        threading.Thread(target=self.server.serve_forever, args=(0.05,), daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


class GenerateTest(unittest.TestCase):
    def setUp(self):
        # Retry without waiting. RetryTest checks the real delays.
        delays = patch.object(inference, 'RETRY_DELAYS_S', (0, 0))
        delays.start()
        self.addCleanup(delays.stop)

    def serve(self, **kwargs):
        server = FakeServer(**kwargs)
        self.addCleanup(server.close)
        env = patch.dict(os.environ, {'GPU_API_URL': server.url + '/'})
        env.start()
        self.addCleanup(env.stop)
        return server

    def test_success_sends_benchmark_settings_and_keeps_usage(self):
        server = self.serve()
        result = generate(MESSAGES, seed=7, max_tokens=256)

        path, body = server.requests[0]
        self.assertEqual(path, '/v1/chat/completions')
        self.assertEqual(body, {'messages': MESSAGES, 'seed': 7, 'temperature': 0.0, 'max_tokens': 256,
                                'cache_prompt': False})
        self.assertIsInstance(result, Generation)
        self.assertEqual(result.text, REPLY['choices'][0]['message']['content'])
        self.assertEqual((result.prompt_tokens, result.completion_tokens), (31, 17))
        self.assertEqual(result.model_id, 'llama-3.1-8b-instruct-q4km')
        self.assertEqual(result.finish_reason, 'stop')
        self.assertEqual(result.retries, 0)
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_multi_turn_messages_are_sent_in_order(self):
        server = self.serve()
        messages = MESSAGES + [{'role': 'assistant', 'content': 'def solve(a, b) return'},
                               {'role': 'user', 'content': 'SyntaxError at 1:16. Fix it.'}]
        generate(messages, seed=0, max_tokens=64)
        self.assertEqual(server.requests[0][1]['messages'], messages)

    def test_server_error_is_retried_then_raises_inference_error(self):
        server = self.serve(status=500)
        with self.assertRaises(InferenceError) as caught:
            generate(MESSAGES, seed=0, max_tokens=64)
        self.assertNotIsInstance(caught.exception, InferenceTimeout)
        self.assertIn('500', str(caught.exception))
        self.assertEqual(len(server.requests), 3)

    def test_server_error_then_success_returns_the_success(self):
        server = self.serve(status=[503, 200])
        result = generate(MESSAGES, seed=0, max_tokens=64)

        self.assertEqual(len(server.requests), 2)
        self.assertEqual(server.requests[0], server.requests[1])
        self.assertEqual((result.prompt_tokens, result.completion_tokens, result.retries), (31, 17, 1))

    def test_client_error_is_not_retried(self):
        server = self.serve(status=400)
        with self.assertRaises(InferenceError) as caught:
            generate(MESSAGES, seed=0, max_tokens=64)
        self.assertIn('400', str(caught.exception))
        self.assertEqual(len(server.requests), 1)

    def test_slow_server_raises_inference_timeout_after_three_tries(self):
        server = self.serve(delay_s=1.0)
        with self.assertRaises(InferenceTimeout):
            generate(MESSAGES, seed=0, max_tokens=64, timeout_s=0.2)
        self.assertEqual(len(server.requests), 3)

    def test_unreachable_server_raises_inference_error(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with patch.dict(os.environ, {'GPU_API_URL': f'http://127.0.0.1:{port}'}):
            with self.assertRaises(InferenceError):
                generate(MESSAGES, seed=0, max_tokens=64)

    def test_missing_usage_raises_instead_of_estimating(self):
        server = self.serve(body={key: value for key, value in REPLY.items() if key != 'usage'})
        with self.assertRaises(InferenceError):
            generate(MESSAGES, seed=0, max_tokens=64)
        self.assertEqual(len(server.requests), 1)

    def test_unset_url_raises(self):
        with patch.dict(os.environ, {'GPU_API_URL': ''}):
            with self.assertRaises(InferenceError):
                generate(MESSAGES, seed=0, max_tokens=64)


class RetryTest(unittest.TestCase):
    """The retry loop with one faked request per try and a faked sleep."""

    def generate(self, outcomes):
        with patch.dict(os.environ, {'GPU_API_URL': 'http://gpu.test'}), \
                patch.object(inference, '_post', side_effect=outcomes) as post, \
                patch.object(inference.time, 'sleep') as sleep:
            try:
                return generate(MESSAGES, seed=0, max_tokens=64), post, sleep
            except InferenceError as error:
                return error, post, sleep

    def test_timeout_then_success_waits_once(self):
        result, post, sleep = self.generate([InferenceTimeout('slow'), REPLY])

        self.assertEqual((result.prompt_tokens, result.completion_tokens, result.retries), (31, 17, 1))
        self.assertEqual(post.call_count, 2)
        sleep.assert_called_once_with(inference.RETRY_DELAYS_S[0])

    def test_three_transient_failures_raise_the_last_one_after_both_delays(self):
        error, post, sleep = self.generate([InferenceTimeout('slow'), InferenceTimeout('slow'),
                                            InferenceTimeout('still slow')])

        self.assertIsInstance(error, InferenceTimeout)
        self.assertEqual(str(error), 'still slow')
        self.assertEqual(post.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], list(inference.RETRY_DELAYS_S))

    def test_permanent_failure_is_not_retried(self):
        error, post, sleep = self.generate([InferenceError('llama-server returned HTTP 400'), REPLY])

        self.assertEqual(str(error), 'llama-server returned HTTP 400')
        self.assertEqual(post.call_count, 1)
        sleep.assert_not_called()


class PostTest(unittest.TestCase):
    """Which single-request failures count as transient."""

    def post_error(self, raised):
        with patch.object(inference.urllib.request, 'urlopen', side_effect=raised):
            with self.assertRaises(InferenceError) as caught:
                inference._post(object(), 1.0)
        return caught.exception

    def test_dropped_connection_is_transient(self):
        self.assertTrue(self.post_error(ConnectionResetError()).transient)
        self.assertTrue(self.post_error(urllib.error.URLError(ConnectionRefusedError())).transient)

    def test_timeout_is_transient(self):
        error = self.post_error(urllib.error.URLError(TimeoutError()))
        self.assertIsInstance(error, InferenceTimeout)
        self.assertTrue(error.transient)

    def test_bad_json_is_not_transient(self):
        self.assertFalse(self.post_error(ValueError('bad json')).transient)


if __name__ == '__main__':
    unittest.main()
