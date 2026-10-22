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
from unittest.mock import patch

from zakbench.runners.inference import Generation, InferenceError, InferenceTimeout, generate

MESSAGES = [{'role': 'user', 'content': 'Write solve(a, b) that returns a + b.'}]
REPLY = {
    'model': 'llama-3.1-8b-instruct-q4km',
    'choices': [{'message': {'role': 'assistant', 'content': 'def solve(a, b):\n    return a + b\n'},
                 'finish_reason': 'stop'}],
    'usage': {'prompt_tokens': 31, 'completion_tokens': 17, 'total_tokens': 48},
}


class FakeServer:
    """llama-server stand-in that records requests and answers with a fixed status, body and delay."""

    def __init__(self, status=200, body=REPLY, delay_s=0.0):
        self.requests = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers['Content-Length'])
                fake.requests.append((self.path, json.loads(self.rfile.read(length))))
                time.sleep(delay_s)
                payload = json.dumps(body).encode()
                try:
                    self.send_response(status)
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
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_multi_turn_messages_are_sent_in_order(self):
        server = self.serve()
        messages = MESSAGES + [{'role': 'assistant', 'content': 'def solve(a, b) return'},
                               {'role': 'user', 'content': 'SyntaxError at 1:16. Fix it.'}]
        generate(messages, seed=0, max_tokens=64)
        self.assertEqual(server.requests[0][1]['messages'], messages)

    def test_http_error_raises_inference_error(self):
        self.serve(status=500, body={'error': 'boom'})
        with self.assertRaises(InferenceError) as caught:
            generate(MESSAGES, seed=0, max_tokens=64)
        self.assertNotIsInstance(caught.exception, InferenceTimeout)
        self.assertIn('500', str(caught.exception))

    def test_slow_server_raises_inference_timeout(self):
        self.serve(delay_s=1.0)
        with self.assertRaises(InferenceTimeout):
            generate(MESSAGES, seed=0, max_tokens=64, timeout_s=0.2)

    def test_unreachable_server_raises_inference_error(self):
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        with patch.dict(os.environ, {'GPU_API_URL': f'http://127.0.0.1:{port}'}):
            with self.assertRaises(InferenceError):
                generate(MESSAGES, seed=0, max_tokens=64)

    def test_missing_usage_raises_instead_of_estimating(self):
        self.serve(body={key: value for key, value in REPLY.items() if key != 'usage'})
        with self.assertRaises(InferenceError):
            generate(MESSAGES, seed=0, max_tokens=64)

    def test_unset_url_raises(self):
        with patch.dict(os.environ, {'GPU_API_URL': ''}):
            with self.assertRaises(InferenceError):
                generate(MESSAGES, seed=0, max_tokens=64)


if __name__ == '__main__':
    unittest.main()
