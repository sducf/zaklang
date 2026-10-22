"""Unit tests for the Docker sandbox."""

from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from sandbox import runner
from sandbox.grade import grade


class TestRunner(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        self.root = Path(self.tmp.name) / "tasks"
        self.root.mkdir()

        self.folder = self.root / "sample_task"
        self.folder.mkdir()

        self.task = {
            "id": "sample_task",
            "functionName": "solve",
        }

        (self.folder / "task.json").write_text(
            json.dumps(self.task)
        )

        self.cases = [
            {"inputs": [i], "expected": i * 2}
            for i in range(5)
        ]

        (self.folder / "hidden_tests.json").write_text(
            json.dumps(self.cases)
        )

        self.inputs_path = Path(self.tmp.name) / "inputs.json"

        self.inputs_path.write_text(
            json.dumps([case["inputs"] for case in self.cases])
        )

    def test_task_allowlist(self):
        self.assertEqual(
            runner._safe_task("sample_task", self.root)[2],
            5,
        )

        for bad in [
            "../sample_task",
            "sample-task",
            "../..",
            "SAMPLE_TASK",
        ]:
            with self.assertRaises(ValueError):
                runner._safe_task(bad, self.root)

    def test_python_syntax_rejected_without_docker(self):
        with patch.object(runner, "_execute") as docker:
            result = runner.evaluate(
                "def solve(: pass",
                "sample_task",
                tasks_root=self.root,
            )

        self.assertEqual(result.outcome, "not_run")
        self.assertFalse(result.compile_ok)
        docker.assert_not_called()

    def test_valid_python_goes_to_worker(self):
        mock_result = runner.SandboxResult(
            "pass", 5, 5, 42
        )

        with patch.object(
            runner,
            "_execute",
            return_value=mock_result,
        ) as docker:
            result = runner.evaluate(
                "def solve(n): return n*2",
                "sample_task",
                tasks_root=self.root,
            )

        self.assertEqual(result.outcome, "pass")
        self.assertTrue(result.compile_ok)
        docker.assert_called_once()

    def test_grader_correct_and_incorrect_trusted_code(self):
        source = Path(self.tmp.name) / "reference.py"

        source.write_text("def solve(n): return n*2\n")

        report = grade(
            source,
            self.folder / "task.json",
            self.inputs_path,
        )

        passed, failed = runner._score_report(
            report,
            self.cases,
        )

        self.assertEqual((passed, failed), (5, []))

        source.write_text("def solve(n): return n\n")

        report = grade(
            source,
            self.folder / "task.json",
            self.inputs_path,
        )

        passed, failed = runner._score_report(
            report,
            self.cases,
        )

        self.assertEqual(
            (passed, failed),
            (1, [2, 3, 4, 5]),
        )

    def test_host_does_not_trust_a_forged_pass(self):
        # Even a forged report must match the hidden answers. -H
        forged = {
            "results": [
                {"ok": True, "value": 0}
                for _ in self.cases
            ]
        }

        passed, failed = runner._score_report(
            forged,
            self.cases,
        )

        self.assertEqual(
            (passed, failed),
            (1, [2, 3, 4, 5]),
        )

        with self.assertRaises(ValueError):
            runner._score_report(
                {"results": []},
                self.cases,
            )

    def test_docker_security_flags_and_cleanup(self):
        calls = []

        def fake_docker(*args, **kwargs):
            calls.append(args)

            if args[0] == "run":
                mounts = [
                    args[i + 1]
                    for i, flag in enumerate(args[:-1])
                    if flag == "--mount"
                ]

                self.assertEqual(len(mounts), 3)

                # Hidden expected answers must not be mounted. -H
                self.assertFalse(
                    any("hidden_tests.json" in m for m in mounts)
                )

                input_mount = next(
                    m for m in mounts
                    if "target=/job/inputs.json" in m
                )

                input_path = (
                    input_mount.split(",")[1]
                    .removeprefix("source=")
                )

                self.assertEqual(
                    json.loads(Path(input_path).read_text()),
                    [[i] for i in range(5)],
                )

                self.assertNotIn(
                    '"expected"',
                    Path(input_path).read_text(),
                )

                return type("R", (), {"stdout": "fake-id"})()

            if args[0] == "wait":
                return type("R", (), {"stdout": "0\n"})()

            if args[0] == "inspect":
                return type("R", (), {
                    "stdout": json.dumps({
                        "OOMKilled": False
                    })
                })()

            if args[0] == "logs":
                return type("R", (), {
                    "stdout": json.dumps({
                        "results": [
                            {"ok": True, "value": i * 2}
                            for i in range(5)
                        ]
                    })
                })()

            raise AssertionError(args)

        with patch.object(
            runner,
            "_docker",
            side_effect=fake_docker,
        ), patch.object(
            runner.subprocess,
            "run",
        ) as cleanup:
            result = runner.evaluate(
                "def solve(n): return n*2",
                "sample_task",
                tasks_root=self.root,
            )

        self.assertEqual(result.outcome, "pass")

        flags = calls[0]

        for flag in [
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", "256m",
            "--cpus", "1",
            "--pids-limit", "64",
            "--user", "65532:65532",
        ]:
            self.assertIn(flag, flags)

        self.assertEqual(flags.count("--mount"), 3)
        self.assertNotIn("hidden_tests.json", repr(flags))

        cleanup.assert_called_once()

        self.assertEqual(
            cleanup.call_args.args[0][:3],
            ["docker", "rm", "-f"],
        )

    def test_timeout_result_and_cleanup(self):

        def fake_docker(*args, **kwargs):
            if args[0] == "run":
                return type("R", (), {"stdout": "fake-id"})()

            raise runner.subprocess.TimeoutExpired(
                cmd=["docker", "wait"],
                timeout=1,
            )

        with patch.object(
            runner,
            "_docker",
            side_effect=fake_docker,
        ), patch.object(
            runner.subprocess,
            "run",
        ) as cleanup:
            result = runner.evaluate(
                "def solve(n): return n*2",
                "sample_task",
                tasks_root=self.root,
                timeout_s=1,
            )

        self.assertEqual(result.outcome, "timeout")
        cleanup.assert_called_once()

    def test_oom_from_docker_state(self):

        def fake_docker(*args, **kwargs):
            if args[0] == "wait":
                return type("R", (), {"stdout": "137\n"})()

            if args[0] == "inspect":
                return type("R", (), {
                    "stdout": json.dumps({
                        "OOMKilled": True
                    })
                })()

            return type("R", (), {"stdout": "fake-id"})()

        with patch.object(
            runner,
            "_docker",
            side_effect=fake_docker,
        ), patch.object(
            runner.subprocess,
            "run",
        ):
            result = runner.evaluate(
                "def solve(n): return n*2",
                "sample_task",
                tasks_root=self.root,
            )

        self.assertEqual(result.outcome, "oom")

    def test_output_does_not_include_hidden_expected_values(self):
        source = Path(self.tmp.name) / "reference.py"

        source.write_text(
            "def solve(n): print('private value'); return -999\n"
        )

        report = grade(
            source,
            self.folder / "task.json",
            self.inputs_path,
        )

        self.assertNotIn(
            "private value",
            json.dumps(report),
        )

        self.assertNotIn(
            '"expected"',
            json.dumps(report),
        )


if __name__ == "__main__":
    unittest.main()