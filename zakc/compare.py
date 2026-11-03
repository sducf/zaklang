"""Compare zakc with the existing compiler and optionally execute in Docker.

From the repository root:
    .venv/bin/python zakc/compare.py --docker

The compiler implementation itself is entirely Rust. This development harness
reuses the migrated test cases and sandbox as independent oracles.
"""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from compiler.src import compile as python_compile
from sandbox.runner import evaluate, execute_program


def parameter_cases(path):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or len(decorator.args) < 2:
                continue
            try:
                names = ast.literal_eval(decorator.args[0]).split(",")
                values = ast.literal_eval(decorator.args[1])
            except (ValueError, TypeError, AttributeError):
                continue
            if "source" not in names:
                continue
            for value in values:
                yield dict(zip(names, (value,) if len(names) == 1 else value))


def main():
    args = argparse.ArgumentParser()
    args.add_argument("--docker", action="store_true")
    args.add_argument("--binary", type=Path, default=ROOT / "zakc/target/debug/zakc")
    args.add_argument("--report", type=Path)
    options = args.parse_args()

    def rust(source, emit="check"):
        process = subprocess.run([str(options.binary), "--json", "--emit", emit, "-"],
                                 input=source, text=True, capture_output=True, timeout=10)
        assert process.returncode in (0, 1), process.stderr
        report, = json.loads(process.stdout)
        assert (process.returncode == 0) == report["ok"]
        return report

    cases = []
    for name in ("compile.json", "semantic.json"):
        groups = json.loads((ROOT / "zakc/tests/cases" / name).read_text(encoding="utf-8"))
        for rows in groups.values():
            for row in rows:
                cases.append({"source": row} if isinstance(row, str)
                             else {"source": row[0], "code": row[1]})
    cases.extend(parameter_cases(ROOT / "zakc/tests/test_transpiler.py"))
    sources = list(dict.fromkeys(case["source"] for case in cases))
    fixtures = sorted((ROOT / "zakc/tests/conformance").glob("*.zak"))
    references = sorted((ROOT / "zakbench/tasks").glob("*/reference.zak"))
    tasks = sorted((ROOT / "zakbench/tasks").glob("*/task.json"))
    assert len(fixtures) == 15 and tasks
    assert {path.parent for path in references} == {path.parent for path in tasks}
    failures = []
    emitted = {}
    for source in sources + [path.read_text(encoding="utf-8") for path in fixtures + references]:
        baseline = python_compile(source)
        result = rust(source, "python")
        if result["ok"] != baseline.ok:
            failures.append({"source": source, "issue": "acceptance mismatch", "rust": result})
            continue
        if baseline.ok:
            generated = result["output"]
            ast.parse(generated, feature_version=(3, 12))
            compile(generated, "<zakc-output>", "exec")
            emitted[source] = generated
        else:
            rust_codes = {error["code"] for error in result["errors"]}
            python_codes = {error.code for error in baseline.errors}
            if rust_codes != python_codes:
                failures.append({"source": source, "issue": "diagnostic code mismatch",
                                 "python": sorted(python_codes), "rust": sorted(rust_codes)})
            if not all(error["span"] and error["span"]["line"] > 0 and error["sources"]
                       for error in result["errors"]):
                failures.append({"source": source, "issue": "missing source coordinates/trace"})
    summary = {"source_cases": len(sources), "corpus_programs": len(fixtures),
               "references": len(references), "failures": failures}
    print(json.dumps(summary, indent=2), flush=True)
    assert not failures, "Compiler parity failed"

    if options.docker:
        for path in fixtures:
            result = execute_program(emitted[path.read_text(encoding="utf-8")])
            assert result.outcome == "pass", (path.stem, result.outcome)
            assert result.stdout == path.with_suffix(".expected").read_bytes(), path.stem
        print("Docker stdout fixtures: 15/15", flush=True)
        total = 0
        for path in references:
            result = evaluate(emitted[path.read_text(encoding="utf-8")], path.parent.name, "python")
            assert result.outcome == "pass", (path.parent.name, result.outcome)
            assert result.tests_passed == result.tests_total
            total += result.tests_total
        summary["hidden_cases_passed"] = total
        print(f"Docker Zak references: {len(references)}/{len(references)}, {total} hidden cases passed", flush=True)
        examples = [case for case in cases if "expected" in case]
        for index, case in enumerate(examples, start=1):
            result = execute_program(emitted[case["source"]])
            assert result.outcome == "pass", (index, result.outcome)
            assert result.stdout.decode("utf-8") == case["expected"], index
        summary["runtime_examples_passed"] = len(examples)
        print(f"Docker semantic examples: {len(examples)}/{len(examples)}", flush=True)
    if options.report:
        options.report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
