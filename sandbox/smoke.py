"""Smoke tests for the Docker sandbox."""

import argparse

from .runner import DEFAULT_TASKS, evaluate


def _expect(
    label: str,
    source: str,
    expected: str,
    *,
    timeout_s=5,
    language="python",
):
    result = evaluate(
        source,
        "array_sum",
        language,
        timeout_s=timeout_s,
    )

    ok = result.outcome == expected

    print(
        f"{label}: {'PASS' if ok else 'FAIL'} "
        f"(outcome={result.outcome}, "
        f"tests={result.tests_passed}/{result.tests_total})"
    )

    return ok


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also check all available Python and Zak references",
    )

    args = parser.parse_args(argv)

    reference = (
        DEFAULT_TASKS / "array_sum" / "reference.py"
    ).read_text(encoding="utf-8")

    checks = [
        _expect(
            "Correct reference",
            reference,
            "pass",
        ),
        _expect(
            "Incorrect implementation",
            "def solve(nums):\n    return 999999\n",
            "fail",
        ),
        _expect(
            "Infinite loop",
            "def solve(nums):\n    while True: pass\n",
            "timeout",
            timeout_s=2,
        ),
        _expect(
            "Abrupt crash",
            "import os\nos._exit(3)\ndef solve(nums): return 0\n",
            "crash",
        ),
    ]

    if args.full:
        for folder in sorted(
            path
            for path in DEFAULT_TASKS.iterdir()
            if path.is_dir()
            and (path / "reference.py").is_file()
        ):
            source = (
                folder / "reference.py"
            ).read_text(encoding="utf-8")

            result = evaluate(source, folder.name)

            success = result.outcome == "pass"

            print(
                f"Python {folder.name}: "
                f"{'PASS' if success else 'FAIL'} "
                f"({result.outcome})"
            )

            checks.append(success)

            zak_path = folder / "reference.zak"

            if zak_path.is_file():
                result = evaluate(
                    zak_path.read_text(encoding="utf-8"),
                    folder.name,
                    "zak",
                )

                success = result.outcome == "pass"

                print(
                    f"Zak {folder.name}: "
                    f"{'PASS' if success else 'FAIL'} "
                    f"({result.outcome})"
                )

                checks.append(success)

    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())