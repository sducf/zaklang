import json
import unittest
from unittest.mock import patch, MagicMock

from spec.count_tokens import extract_sections, count_tokens, LIMIT


class TestCountTokens(unittest.TestCase):

    def test_extract_sections(self):
        text = (
            "# Zak Core v0.1\n"
            "## zak_spec\n"
            "x:=1\n"
            "## zak_examples\n"
            "@f()I{^1}\n"
        )

        spec, examples = extract_sections(text)

        self.assertEqual(spec, "x:=1")
        self.assertEqual(examples, "@f()I{^1}")

    @patch("urllib.request.urlopen")
    def test_count_tokens(self, mock_urlopen):
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({
            "tokens": [1, 2, 3, 4, 5]
        }).encode("utf-8")

        mock_urlopen.return_value = response

        result = count_tokens(
            "http://localhost:8080",
            "x:=1"
        )

        self.assertEqual(result, 5)

        request = mock_urlopen.call_args.args[0]

        self.assertEqual(
            request.full_url,
            "http://localhost:8080/tokenize"
        )

        payload = json.loads(request.data.decode("utf-8"))

        self.assertEqual(payload["content"], "x:=1")
        self.assertFalse(payload["add_special"])

    @patch("spec.count_tokens.count_tokens")
    @patch("sys.argv", [
        "count_tokens.py",
        "--endpoint", "http://localhost:8080",
        "--model-id", "Llama-3.1-8B-Instruct-Q4_K_M",
    ])
    def test_token_limit(self, mock_count_tokens):
        from spec.count_tokens import main

        for token_count, should_pass in [
            (1199, True),
            (1200, False),
            (1201, False),
        ]:
            with self.subTest(token_count=token_count):
                mock_count_tokens.return_value = token_count

                if should_pass:
                    main()
                else:
                    with self.assertRaises(SystemExit) as context:
                        main()

                    self.assertEqual(context.exception.code, 1)
if __name__ == "__main__":
    unittest.main()