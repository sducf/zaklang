"""Trusted-side Docker sandbox runner for SD-21.

The backend must authenticate users and own/persist benchmark runs.
This module is a local execution library, not a public API endpoint.
"""

import argparse
from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
from uuid import uuid4


IMAGE = "zaklang-sandbox:latest"

DEFAULT_TASKS = (
    Path(__file__).resolve().parents[1] / "zakbench" / "tasks"
)

TASK_ID = re.compile(r"[a-z0-9_]+\Z")

MAX_SOURCE_BYTES = 20_000
MAX_OUTPUT_BYTES = 65_536


@dataclass
class ProgramResult:
    """A standalone execution; 'pass' means exit zero, not a stdout comparison."""

    outcome: str
    stdout: bytes = b""
    stderr: bytes = b""
    exit_code: int | None = None
    execution_ms: float = 0.0
    detail: str | None = None


@dataclass
class SandboxResult:
    outcome: str
    tests_passed: int
    tests_total: int
    execution_ms: float
    failed_tests: list[int] = field(default_factory=list)
    detail: str | None = None
    compile_ok: bool | None = None
    compile_errors: list[dict] = field(default_factory=list)
    transpiled_python: str | None = None
    # Candidate's own value for the first failing test, as JSON; None if it raised. -H
    first_failure_actual: str | None = None


def _docker(*args: str, timeout: float = 20, binary: bool = False):
    """Run a trusted Docker CLI command."""

    try:
        result = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=not binary,
            timeout=timeout,
            **({} if binary else {"encoding": "utf-8", "errors": "replace"}),
        )

    except FileNotFoundError as exc:
        raise RuntimeError(
            "Docker CLI not installed. Install/start Docker Desktop."
        ) from exc

    if result.returncode != 0:
        # Diagnostics are for the trusted worker, never the public UI. -H
        diagnostic = result.stderr
        if binary:
            diagnostic = diagnostic.decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Docker {args[0]} failed (exit {result.returncode}): "
            + diagnostic.strip()[:300]
        )

    return result


def _safe_task(task_id: str, tasks_root: Path):
    """Validate task IDs and prevent path traversal."""

    if not TASK_ID.fullmatch(task_id):
        raise ValueError("Invalid task ID")

    root = tasks_root.resolve(strict=True)

    folder = (root / task_id).resolve(strict=True)

    if folder.parent != root:
        raise ValueError("Task directory must be a direct child")

    task_file = (folder / "task.json").resolve(strict=True)
    test_file = (folder / "hidden_tests.json").resolve(strict=True)

    if task_file.parent != folder or test_file.parent != folder:
        raise ValueError("Task fixtures cannot point outside task folder")

    task = json.loads(task_file.read_text(encoding="utf-8"))
    cases = json.loads(test_file.read_text(encoding="utf-8"))

    if task.get("id") != task_id:
        raise ValueError("Task ID does not match its folder")

    if not isinstance(cases, list) or not 5 <= len(cases) <= 12:
        raise ValueError("Invalid hidden test count")

    return task_file, test_file, len(cases)


def _mount(path: Path, target: str) -> str:
    """Mount one file read-only instead of mounting the repository."""

    return (
        f"type=bind,source={path.resolve()},"
        f"target={target},readonly"
    )


def _score_report(report: dict, cases: list) -> tuple[int, list[int]]:
    """Compare untrusted candidate output to hidden answers on the host."""

    if not isinstance(report, dict) or set(report) != {"results"}:
        raise ValueError("Invalid execution report")

    entries = report["results"]

    if not isinstance(entries, list) or len(entries) != len(cases):
        raise ValueError("Execution result count does not match hidden cases")

    failed = []

    for index, (entry, case) in enumerate(zip(entries, cases), start=1):
        if not isinstance(entry, dict) or type(entry.get("ok")) is not bool:
            raise ValueError("Invalid test result entry")

        if entry["ok"]:
            if set(entry) != {"ok", "value"}:
                raise ValueError("Invalid successful test entry")

            # Only the trusted host knows the expected answer. -H
            correct = entry["value"] == case["expected"]

        else:
            if set(entry) != {"ok"}:
                raise ValueError("Invalid unsuccessful test entry")

            correct = False

        if not correct:
            failed.append(index)

    return len(cases) - len(failed), failed


def _execute(
    source: str,
    task_file: Path,
    test_file: Path,
    tests_total: int,
    *,
    image: str,
    timeout_s: float,
) -> SandboxResult:
    # Read hidden expected answers only in the trusted process. -H
    cases = json.loads(test_file.read_text(encoding="utf-8"))

    if not isinstance(cases, list) or len(cases) != tests_total:
        raise ValueError("Invalid hidden test file")

    inputs_only = []

    for case in cases:
        if (
            not isinstance(case, dict)
            or not isinstance(case.get("inputs"), list)
            or "expected" not in case
        ):
            raise ValueError("Invalid hidden test case")

        inputs_only.append(case["inputs"])

    with tempfile.TemporaryDirectory(prefix="zaklang-sd21-") as tmp:
        solution = Path(tmp) / "solution.py"
        inputs = Path(tmp) / "inputs.json"
        solution.write_text(source, encoding="utf-8")
        # Only test arguments, never expected values, enter Docker.
        inputs.write_text(json.dumps(inputs_only), encoding="utf-8")
        execution = _run_container(
            [(solution, "/job/solution.py"), (task_file, "/job/task.json"),
             (inputs, "/job/inputs.json")],
            image=image, timeout_s=timeout_s, report_only=True,
        )

    if execution.outcome != "pass":
        return SandboxResult(execution.outcome, 0, tests_total, execution.execution_ms,
                             detail=execution.detail)

    try:
        log = execution.stdout.strip()
        if len(log) > MAX_OUTPUT_BYTES:
            raise ValueError("Execution report too large")
        report = json.loads(log)
        passed, failed = _score_report(report, cases)
        actual = None
        if failed:
            entry = report["results"][failed[0] - 1]
            if entry["ok"]:
                actual = json.dumps(entry["value"], separators=(",", ":"))
        return SandboxResult(
            "fail" if failed else "pass", passed, tests_total,
            execution.execution_ms, failed, first_failure_actual=actual,
        )
    except (ValueError, TypeError, KeyError, UnicodeDecodeError):
        return SandboxResult(
            "crash", 0, tests_total, execution.execution_ms,
            detail="Container did not produce a valid execution report",
        )


def _run_container(
    mounts: list[tuple[Path, str]], *, image: str, timeout_s: float,
    command: tuple[str, ...] = (), report_only: bool = False,
) -> ProgramResult:
    """Shared isolated execution and cleanup for programs and task grading."""
    started = time.monotonic()
    name = "zaklang-sandbox-" + uuid4().hex[:16]

    docker_command = [
        "run",
        "--detach",
        "--pull", "never",
        "--name", name,
        "--network", "none",
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--memory", "256m",
        "--memory-swap", "256m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
        "--user", "65532:65532",
        "--workdir", "/job",
        "--log-driver", "local",
        "--log-opt", "max-size=1m",
        "--log-opt", "max-file=2",

        *[argument for path, target in mounts
          for argument in ("--mount", _mount(path, target))],
        image,
        *command,
    ]

    try:
        _docker(*docker_command, timeout=20)
        try:
            waited = _docker("wait", name, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            return ProgramResult(
                "timeout", execution_ms=(time.monotonic() - started) * 1000,
                detail=f"Exceeded {timeout_s:g}s execution limit",
            )

        exit_code = int(waited.stdout.strip())
        state = json.loads(_docker("inspect", "--format", "{{json .State}}", name).stdout)
        if state.get("OOMKilled"):
            return ProgramResult(
                "oom", exit_code=exit_code,
                execution_ms=(time.monotonic() - started) * 1000,
                detail="Container exceeded memory limit",
            )
        # Task grading consumes its final JSON report; standalone programs
        # preserve every stdout byte without decoding or newline translation.
        log_options = ("--tail", "1") if report_only else ()
        logs = _docker("logs", *log_options, name, binary=True)
        return ProgramResult(
            "pass" if exit_code == 0 else "crash",
            stdout=logs.stdout, stderr=logs.stderr, exit_code=exit_code,
            execution_ms=(time.monotonic() - started) * 1000,
            detail=None if exit_code == 0 else f"Program exited with code {exit_code}",
        )
    finally:
        try:
            subprocess.run(
                ["docker", "rm", "-f", name], timeout=10,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass


def execute_program(
    source: str, *, image: str = IMAGE, timeout_s: float = 5.0,
) -> ProgramResult:
    """Syntax-check standalone Python, then execute only inside Docker.

    Stdout and stderr are separate byte streams. The caller compares stdout
    with its expected bytes on the host. Missing Docker/image errors propagate.
    """
    if not 0 < timeout_s <= 60:
        raise ValueError("timeout_s must be between 0 and 60 seconds")
    if not source.strip() or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("Source must be 1–20,000 UTF-8 bytes")
    try:
        compile(source, "<candidate>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        return ProgramResult("not_run", detail=f"Python syntax error at {exc.lineno}:{exc.offset}")

    with tempfile.TemporaryDirectory(prefix="zaklang-program-") as tmp:
        solution = Path(tmp) / "solution.py"
        solution.write_text(source, encoding="utf-8")
        result = _run_container(
            [(solution, "/job/solution.py")], image=image, timeout_s=timeout_s,
            command=("python", "-I", "/job/solution.py"),
        )
    if len(result.stdout) + len(result.stderr) > MAX_OUTPUT_BYTES:
        result.outcome = "crash"
        result.detail = f"Program output exceeded {MAX_OUTPUT_BYTES} bytes"
        result.stdout = result.stdout[:MAX_OUTPUT_BYTES]
        result.stderr = result.stderr[:MAX_OUTPUT_BYTES - len(result.stdout)]
    return result


def evaluate(
    source: str,
    task_id: str,
    language: str = "python",
    *,
    tasks_root: Path = DEFAULT_TASKS,
    image: str = IMAGE,
    timeout_s: float = 5.0,
) -> SandboxResult:
    """Validate and execute a Python or Zak candidate."""

    if timeout_s <= 0 or timeout_s > 60:
        raise ValueError(
            "timeout_s must be between 0 and 60 seconds"
        )

    if language not in {"python", "zak"}:
        raise ValueError(
            "language must be 'python' or 'zak'"
        )

    if (
        not source.strip()
        or len(source.encode("utf-8")) > MAX_SOURCE_BYTES
    ):
        raise ValueError(
            "Source must be 1–20,000 UTF-8 bytes"
        )

    task_file, test_file, tests_total = _safe_task(
        task_id,
        Path(tasks_root),
    )

    transpiled = None

    if language == "zak":
        # Compile Zak on the trusted side; do not execute it here. -H
        from compiler.src import (
            compile as zak_compile,
            transpile,
        )

        checked = zak_compile(source)

        if not checked.ok or checked.ast is None:
            return SandboxResult(
                outcome="not_run",
                tests_passed=0,
                tests_total=tests_total,
                execution_ms=0,
                compile_ok=False,
                compile_errors=[
                    {
                        "line": error.line,
                        "col": error.col,
                        "code": error.code,
                        "message": error.message,
                    }
                    for error in checked.errors
                ],
            )

        try:
            source = transpile(checked.ast)

        except Exception:
            return SandboxResult(
                outcome="not_run",
                tests_passed=0,
                tests_total=tests_total,
                execution_ms=0,
                compile_ok=False,
                detail="Zak transpilation failed",
            )

        transpiled = source

    else:
        # Syntax-check only; no user Python is run on the host. -H
        try:
            compile(
                source,
                "<candidate>",
                "exec",
                dont_inherit=True,
            )

        except SyntaxError as exc:
            return SandboxResult(
                outcome="not_run",
                tests_passed=0,
                tests_total=tests_total,
                execution_ms=0,
                compile_ok=False,
                compile_errors=[
                    {
                        "line": exc.lineno or 1,
                        "col": exc.offset or 1,
                        "code": "SYNTAX_ERROR",
                        "message": exc.msg or "Python syntax error",
                    }
                ],
            )

    result = _execute(
        source,
        task_file,
        test_file,
        tests_total,
        image=image,
        timeout_s=timeout_s,
    )

    result.compile_ok = True
    result.transpiled_python = transpiled

    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local Docker sandbox prototype"
    )

    parser.add_argument(
        "--task",
        required=True,
        help="Trusted ZakBench task ID",
    )

    parser.add_argument(
        "--language",
        choices=["python", "zak"],
        required=True,
    )

    parser.add_argument(
        "--file",
        type=Path,
        required=True,
        help="Generated or reference source file",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5,
    )

    parser.add_argument(
        "--image",
        default=IMAGE,
    )

    args = parser.parse_args(argv)

    try:
        result = evaluate(
            args.file.read_text(encoding="utf-8"),
            args.task,
            args.language,
            image=args.image,
            timeout_s=args.timeout,
        )

    except (OSError, RuntimeError, ValueError) as exc:
        print(
            json.dumps({
                "outcome": "not_run",
                "detail": str(exc),
            }),
            file=sys.stderr,
        )
        return 2

    print(json.dumps(asdict(result), indent=2))

    return 0 if result.outcome == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
