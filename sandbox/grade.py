"""Execute candidate code inside the disposable Docker sandbox."""

import contextlib
import json
from pathlib import Path
import runpy
import sys


SOLUTION = Path("/job/solution.py")
TASK = Path("/job/task.json")
INPUTS = Path("/job/inputs.json")

MAX_RESULT_BYTES = 65536
MAX_VALUE_BYTES = 8192


class DiscardOutput:
    """Discard ordinary output produced by candidate code."""

    def write(self, text):
        return len(text)

    def flush(self):
        pass


def grade(
    solution_path=SOLUTION,
    task_path=TASK,
    inputs_path=INPUTS,
):
    # Inputs are available here, but expected answers are not. -H
    task = json.loads(task_path.read_text(encoding="utf-8"))
    test_inputs = json.loads(inputs_path.read_text(encoding="utf-8"))

    function_name = task.get("functionName")

    if not isinstance(function_name, str):
        raise ValueError("Invalid function name")

    if not isinstance(test_inputs, list):
        raise ValueError("Invalid test inputs")

    results = []
    sink = DiscardOutput()

    # All candidate execution occurs inside the isolated container. -H
    with contextlib.redirect_stdout(sink):
        with contextlib.redirect_stderr(sink):
            candidate = runpy.run_path(str(solution_path))
            function = candidate[function_name]

            if not callable(function):
                raise TypeError("Entry point is not callable")

            for args in test_inputs:
                if not isinstance(args, list):
                    raise ValueError("Invalid test input")

                try:
                    value = function(*args)

                    # Only bounded JSON-compatible outputs are accepted. -H
                    encoded = json.dumps(
                        value,
                        allow_nan=False,
                        separators=(",", ":"),
                    )

                    if len(encoded.encode("utf-8")) > MAX_VALUE_BYTES:
                        raise ValueError("Result too large")

                    results.append({
                        "ok": True,
                        "value": value,
                    })

                except Exception:
                    results.append({"ok": False})

    # This report is untrusted until the host validates it. -H
    return {"results": results}


def main():
    try:
        report = grade()
        encoded = json.dumps(
            report,
            allow_nan=False,
            separators=(",", ":"),
        )

        if len(encoded.encode("utf-8")) > MAX_RESULT_BYTES:
            raise ValueError("Report too large")

        print(encoded)
        return 0

    except Exception:
        # Never expose candidate tracebacks or hidden answer values. -H
        print('{"error":"execution_failed"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())