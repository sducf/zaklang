"""Small in-process corpus comparison; excludes startup, file IO, and execution."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from compiler.src import compile as compile_zak, transpile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=200)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("rounds must be positive")
    paths = sorted((ROOT / "compiler/tests/conformance").glob("*.zak"))
    paths += sorted((ROOT / "zakbench/tasks").glob("*/reference.zak"))
    sources = [path.read_text(encoding="utf-8") for path in paths]

    def pipeline(source):
        result = compile_zak(source)
        assert result.ok and result.ast is not None
        ast.parse(transpile(result.ast))

    for source in sources:
        pipeline(source)
    started = time.perf_counter()
    for _ in range(args.rounds):
        for source in sources:
            pipeline(source)
    elapsed = time.perf_counter() - started
    python = {"implementation": "Python", "programs": len(sources), "rounds": args.rounds,
              "compilations": args.rounds * len(sources), "seconds": elapsed,
              "microseconds_per_program": elapsed * 1e6 / (args.rounds * len(sources))}
    binary = ROOT / "zakc/target/release/examples/throughput"
    rust = json.loads(subprocess.check_output([str(binary), str(args.rounds)], text=True))
    report = {"python": python, "rust": rust,
              "ratio_python_seconds_over_rust_seconds": elapsed / rust["seconds"],
              "scope": "25 existing programs; parse + check + emit + Python AST validation, warm in-process"}
    print(json.dumps(report, indent=2))
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
