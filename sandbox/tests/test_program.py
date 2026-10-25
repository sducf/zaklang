"""Standalone execution contracts; candidate code is never executed by these mocks."""

from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from sandbox import runner


def docker_reply(*, stdout=b"hello\r\n\n \xff", stderr=b"diagnostic\n", exit_code=0,
                 oom=False, timeout=False):
    def reply(*args, **kwargs):
        if args[0] == "run":
            return SimpleNamespace(stdout="container-id")
        if args[0] == "wait":
            if timeout:
                raise subprocess.TimeoutExpired("docker wait", 1)
            return SimpleNamespace(stdout=str(exit_code))
        if args[0] == "inspect":
            return SimpleNamespace(stdout='{"OOMKilled": %s}' % str(oom).lower())
        if args[0] == "logs":
            assert kwargs["binary"] is True
            assert "--tail" not in args
            return SimpleNamespace(stdout=stdout, stderr=stderr)
        raise AssertionError(args)
    return reply


def execute(**kwargs):
    with patch.object(runner, "_docker", side_effect=docker_reply(**kwargs)), \
            patch.object(runner.subprocess, "run") as cleanup:
        result = runner.execute_program("print('hello')")
    cleanup.assert_called_once()
    assert cleanup.call_args.args[0][:3] == ["docker", "rm", "-f"]
    return result


def test_program_preserves_all_stdout_bytes_and_separates_stderr():
    result = execute()
    assert result.outcome == "pass"
    assert result.exit_code == 0
    assert result.stdout == b"hello\r\n\n \xff"
    assert result.stderr == b"diagnostic\n"
    assert result.execution_ms >= 0


@pytest.mark.parametrize("stdout", [b"", b"no newline", "café\n".encode(), b" \n\n"])
def test_program_does_not_normalize_output(stdout):
    assert execute(stdout=stdout, stderr=b"").stdout == stdout


def test_program_uses_existing_isolation_with_only_source_mounted():
    reply = docker_reply()

    def inspect_command(*args, **kwargs):
        if args[0] == "run":
            for flag, value in [("--network", "none"), ("--cap-drop", "ALL"),
                                ("--security-opt", "no-new-privileges"),
                                ("--memory", "256m"), ("--memory-swap", "256m"),
                                ("--cpus", "1"), ("--pids-limit", "64"),
                                ("--user", "65532:65532"), ("--pull", "never")]:
                assert args[args.index(flag) + 1] == value
            assert "--read-only" in args
            assert "size=16m" in args[args.index("--tmpfs") + 1]
            assert args.count("--mount") == 1
            mount = args[args.index("--mount") + 1]
            assert mount.endswith("target=/job/solution.py,readonly")
            path = Path(mount.split("source=", 1)[1].split(",", 1)[0])
            assert path.read_text() == "print('hello')"
            assert args[-4:] == ("custom-image", "python", "-I", "/job/solution.py")
        return reply(*args, **kwargs)

    with patch.object(runner, "_docker", side_effect=inspect_command), \
            patch.object(runner.subprocess, "run"):
        runner.execute_program("print('hello')", image="custom-image")


@pytest.mark.parametrize("source", ["", "  \n", "#" * 20_001, "é" * 10_001],
                         ids=["empty", "whitespace", "large-ascii", "large-utf8"])
def test_invalid_source_never_starts_docker(source):
    with patch.object(runner, "_docker") as docker:
        with pytest.raises(ValueError):
            runner.execute_program(source)
    docker.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, 61, float("nan"), float("inf")])
def test_invalid_timeout_never_starts_docker(timeout):
    with patch.object(runner, "_docker") as docker:
        with pytest.raises(ValueError):
            runner.execute_program("pass", timeout_s=timeout)
    docker.assert_not_called()


def test_syntax_error_is_not_executed():
    with patch.object(runner, "_docker") as docker:
        result = runner.execute_program("def broken(:")
    assert result.outcome == "not_run"
    assert result.exit_code is None
    docker.assert_not_called()


@pytest.mark.parametrize(("kwargs", "outcome"), [
    ({"exit_code": 3}, "crash"),
    ({"timeout": True}, "timeout"),
    ({"exit_code": 137, "oom": True}, "oom"),
    ({"stdout": b"x" * 65_537}, "crash"),
    ({"stderr": b"x" * 65_537}, "crash"),
])
def test_unsuccessful_program_and_output_limit_cleanup(kwargs, outcome):
    result = execute(**kwargs)
    assert result.outcome == outcome
    assert len(result.stdout) + len(result.stderr) <= runner.MAX_OUTPUT_BYTES


def test_combined_output_limit_and_exact_boundary():
    assert execute(stdout=b"x" * 65_536, stderr=b"").outcome == "pass"
    result = execute(stdout=b"x" * 40_000, stderr=b"x" * 40_000)
    assert result.outcome == "crash"
    assert len(result.stdout) + len(result.stderr) <= runner.MAX_OUTPUT_BYTES


@pytest.mark.parametrize("stage", ["run", "wait", "inspect", "logs"])
def test_docker_failures_propagate_and_remove_container(stage):
    reply = docker_reply()

    def fail(*args, **kwargs):
        if args[0] == stage:
            raise RuntimeError("Docker unavailable")
        return reply(*args, **kwargs)

    with patch.object(runner, "_docker", side_effect=fail), \
            patch.object(runner.subprocess, "run") as cleanup:
        with pytest.raises(RuntimeError, match="Docker unavailable"):
            runner.execute_program("pass")
    cleanup.assert_called_once()


def test_missing_docker_is_a_failure():
    with patch.object(runner.subprocess, "run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="Docker CLI not installed"):
            runner.execute_program("pass")


def test_docker_binary_mode_disables_text_decoding():
    response = SimpleNamespace(returncode=0, stdout=b"\xff\r\n", stderr=b"")
    with patch.object(runner.subprocess, "run", return_value=response) as run:
        assert runner._docker("logs", "container", binary=True).stdout == b"\xff\r\n"
    assert run.call_args.kwargs.get("text", False) is False
    assert run.call_args.kwargs.get("encoding") is None
