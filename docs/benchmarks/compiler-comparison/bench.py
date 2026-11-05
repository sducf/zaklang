"""Legacy Python compiler vs. zakc (Rust via PyO3): speed, memory, and CPU.

This harness produced docs/benchmarks/compiler-comparison/REPORT.md. It needs
the legacy ``compiler/`` package, which was removed after the measurement, so
it runs only on a checkout that still contains it (commit 712e164 or earlier).

From the repository root:

    cargo build --release --manifest-path zakc/Cargo.toml --bin zakc --example throughput
    RUSTFLAGS="-C target-cpu=native" cargo build --release --manifest-path zakc/Cargo.toml \
      --example throughput --target-dir zakc/target/native   # optional extra data point
    PYO3_PYTHON="$PWD/.venv/bin/python" PYO3_BUILD_EXTENSION_MODULE=1 \
      cargo build --release --manifest-path zakc/Cargo.toml --features python --lib
    mkdir -p zakc/target/python-release
    cp zakc/target/release/libzakc.so zakc/target/python-release/zakc.so
    PERF=/path/to/perf .venv/bin/python docs/benchmarks/compiler-comparison/bench.py \
      --out docs/benchmarks/compiler-comparison/results.json

Every measured workload runs in its own pinned process, so perf counters and
peak RSS describe exactly one implementation. The workload mirrors the backend
call: ``compile`` + ``transpile`` for the legacy package, ``zakc.zak_transpile``
for the Rust extension. Docker execution of the generated Python is excluded.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import re
import resource
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
EXTENSIONS = {
    # zakc as merged on main (712e164), rebuilt with the same release profile.
    "zakc-main": ROOT / "zakc/target/python-baseline",
    # zakc with the precomputed line index replacing pest's line_col.
    "zakc": ROOT / "zakc/target/python-release",
}
IMPLEMENTATIONS = ("legacy", *EXTENSIONS)
CPU = os.environ.get("BENCH_CPU", "4")
PERF_EVENTS = ("task-clock,cycles,instructions,cache-references,cache-misses,"
               "branches,branch-misses,page-faults,context-switches")


def valid_sources() -> list[tuple[str, str]]:
    paths = sorted((ROOT / "zakc/tests/conformance").glob("*.zak"))
    paths += sorted((ROOT / "zakbench/tasks").glob("*/reference.zak"))
    return [(str(path.relative_to(ROOT)), path.read_text(encoding="utf-8")) for path in paths]


def invalid_sources() -> list[tuple[str, str]]:
    sources = []
    for name in ("compile.json", "semantic.json"):
        groups = json.loads((ROOT / "zakc/tests/cases" / name).read_text(encoding="utf-8"))
        for group, rows in groups.items():
            for index, row in enumerate(rows):
                if isinstance(row, list):
                    sources.append((f"{group}[{index}]", row[0]))
    return sources


def corpus(kind: str) -> list[tuple[str, str]]:
    return valid_sources() if kind == "valid" else invalid_sources()


def make_pipeline(implementation: str):
    """Return a function performing the backend's compile call for one source."""
    if implementation == "legacy":
        sys.path.insert(0, str(ROOT))
        from compiler.src import TranspileError, compile as compile_zak, transpile

        def legacy(source: str) -> bool:
            result = compile_zak(source)
            if not result.ok or result.ast is None:
                return False
            try:
                transpile(result.ast)
            except TranspileError:
                return False
            return True

        return legacy

    sys.path.insert(0, str(EXTENSIONS[implementation]))
    import zakc

    def rust(source: str) -> bool:
        try:
            zakc.zak_transpile(source)
        except ValueError:
            return False
        return True

    return rust


def rss_kib() -> int:
    for line in Path("/proc/self/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    raise RuntimeError("VmRSS missing")


def worker(implementation: str, kind: str, rounds: int, mode: str) -> None:
    """Run inside a fresh process; print one JSON object."""
    sources = corpus(kind)
    rss_interpreter = rss_kib()
    started = time.perf_counter()
    pipeline = make_pipeline(implementation)
    import_seconds = time.perf_counter() - started
    rss_imported = rss_kib()

    expected = kind == "valid"
    first_call = time.perf_counter()
    for name, source in sources:
        assert pipeline(source) is expected, (implementation, name)
    first_pass_seconds = time.perf_counter() - first_call

    report: dict = {"implementation": implementation, "corpus": kind, "programs": len(sources),
                    "rounds": rounds, "import_seconds": import_seconds,
                    "first_pass_seconds": first_pass_seconds,
                    "rss_interpreter_kib": rss_interpreter, "rss_after_import_kib": rss_imported}

    if mode == "latency":
        per_program: dict[str, list[float]] = {name: [] for name, _ in sources}
        for _ in range(rounds):
            for name, source in sources:
                tick = time.perf_counter_ns()
                pipeline(source)
                per_program[name].append((time.perf_counter_ns() - tick) / 1000)
        samples = sorted(value for values in per_program.values() for value in values)
        medians = {name: statistics.median(values) for name, values in per_program.items()}
        report["latency_us"] = {
            "p50": samples[len(samples) // 2], "p90": samples[int(len(samples) * 0.90)],
            "p99": samples[int(len(samples) * 0.99)], "max": samples[-1],
            "mean": statistics.fmean(samples)}
        report["slowest_programs_median_us"] = sorted(medians.items(), key=lambda item: -item[1])[:5]
        report["per_program_median_us"] = medians
    elif mode == "throughput":
        started = time.perf_counter()
        for _ in range(rounds):
            for _, source in sources:
                pipeline(source)
        elapsed = time.perf_counter() - started
        report["seconds"] = elapsed
        if rounds:
            report["us_per_program"] = elapsed * 1e6 / (rounds * len(sources))
            report["programs_per_second"] = rounds * len(sources) / elapsed
    elif mode == "tracemalloc":
        import tracemalloc
        peaks = []
        for _, source in sources:
            tracemalloc.start()
            pipeline(source)
            peaks.append(tracemalloc.get_traced_memory()[1])
            tracemalloc.stop()
        report["python_heap_peak_bytes"] = {"median": statistics.median(peaks), "max": max(peaks),
                                            "mean": statistics.fmean(peaks)}

    usage = resource.getrusage(resource.RUSAGE_SELF)
    report["max_rss_kib"] = usage.ru_maxrss
    report["cpu_user_seconds"] = usage.ru_utime
    report["cpu_system_seconds"] = usage.ru_stime
    print(json.dumps(report))


def perf_binary() -> str | None:
    return os.environ.get("PERF")


def parse_perf(stderr: str) -> dict:
    counters = {}
    for line in stderr.splitlines():
        parts = line.split(";")
        if len(parts) >= 3 and parts[2]:
            value, event = parts[0], parts[2]
            try:
                counters[event.removesuffix(":u")] = float(value)
            except ValueError:
                counters[event.removesuffix(":u")] = None
    return counters


def run(command: list[str], *, perf: bool = False, repeat: int = 1) -> tuple[str, dict]:
    prefix = ["taskset", "-c", CPU]
    if perf and perf_binary():
        prefix += [perf_binary(), "stat", "-x", ";", "-r", str(repeat), "-e", PERF_EVENTS, "--"]
    environment = dict(os.environ, PYTHONHASHSEED="0")
    process = subprocess.run(prefix + command, capture_output=True, text=True, env=environment, check=False)
    if process.returncode != 0:
        raise RuntimeError(f"{command} failed:\n{process.stderr}")
    # perf stat -r N runs the child N times; keep the final run's JSON line.
    lines = [line for line in process.stdout.splitlines() if line.strip()]
    return (lines[-1] if lines else ""), parse_perf(process.stderr) if perf else {}


def worker_command(implementation: str, kind: str, rounds: int, mode: str) -> list[str]:
    return [sys.executable, str(Path(__file__).resolve()), "--worker", implementation,
            "--corpus", kind, "--rounds", str(rounds), "--mode", mode]


def cold_start() -> dict:
    """Process start + import + one compile of one reference, repeated."""
    path = ROOT / "zakbench/tasks/array_sum/reference.zak"
    commands = {
        "python_bare": [sys.executable, "-c", "pass"],
        "legacy_import": [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(ROOT)!r}); import compiler.src"],
        "zakc_import": [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(EXTENSIONS['zakc'])!r}); import zakc"],
        "legacy_cli_one_file": [sys.executable, "-m", "compiler.src", str(path)],
        "zakc_cli_one_file": [str(ROOT / "zakc/target/release/zakc"), "--emit", "check", str(path)],
    }
    results = {}
    for name, command in commands.items():
        runs = []
        for _ in range(3):
            run(command)
        for _ in range(20):
            tick = time.perf_counter()
            run(command)
            runs.append(time.perf_counter() - tick)
        _, counters = run(command, perf=True, repeat=10)
        results[name] = {"median_ms": statistics.median(runs) * 1e3, "min_ms": min(runs) * 1e3,
                         "perf": counters}
    return results


def peak_rss_time(command: list[str]) -> int:
    """Peak RSS in KiB, reported by GNU time for the whole child process."""
    process = subprocess.run(["/usr/bin/time", "-f", "%M", *command], capture_output=True, text=True, check=True)
    return int(process.stderr.strip().splitlines()[-1])


def driver(output: Path, legacy_rounds: int, rust_rounds: int) -> None:
    results: dict = {"environment": environment()}
    results["cold_start"] = cold_start()

    native, counters = run([str(ROOT / "zakc/target/release/examples/throughput"), str(rust_rounds * 4)],
                           perf=True, repeat=3)
    results["native_rust_throughput"] = {**json.loads(native), "perf": counters}
    baseline = ROOT / "zakc/target/release/examples/throughput-baseline"
    if baseline.exists():
        native, counters = run([str(baseline), str(rust_rounds * 4)], perf=True, repeat=3)
        results["native_rust_throughput_main"] = {**json.loads(native), "perf": counters}
    # Optional extra data point: RUSTFLAGS="-C target-cpu=native" build in zakc/target/native.
    tuned = ROOT / "zakc/target/native/release/examples/throughput"
    if tuned.exists():
        native, counters = run([str(tuned), str(rust_rounds * 4)], perf=True, repeat=3)
        results["native_rust_throughput_target_cpu_native"] = {**json.loads(native), "perf": counters}

    for kind in ("valid", "invalid"):
        section = results.setdefault(kind, {})
        for implementation in IMPLEMENTATIONS:
            rounds = legacy_rounds if implementation == "legacy" else rust_rounds
            entry = section.setdefault(implementation, {})
            stdout, counters = run(worker_command(implementation, kind, rounds, "throughput"), perf=True, repeat=3)
            entry["throughput"] = json.loads(stdout)
            # Subtract interpreter startup/import so counters describe the compile work only.
            entry["throughput"]["perf"] = counters
            idle, idle_counters = run(worker_command(implementation, kind, 0, "throughput"), perf=True, repeat=5)
            entry["startup_only_perf"] = idle_counters
            entry["latency"] = json.loads(run(worker_command(implementation, kind, max(rounds // 2, 5), "latency"))[0])
            entry["tracemalloc"] = json.loads(run(worker_command(implementation, kind, 1, "tracemalloc"))[0])
            entry["gnu_time_peak_rss_kib"] = peak_rss_time(worker_command(implementation, kind, rounds, "throughput"))
            print(f"{kind}/{implementation}: {entry['throughput']['us_per_program']:.1f} us/program", flush=True)

    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Scaling: how compile time and memory grow with program size and nesting.

WIDTH_FUNCTIONS = (1, 5, 10, 25, 50, 100, 200, 400, 800, 1600, 3200, 6400)
NESTING_DEPTHS = (1, 2, 4, 8, 12, 16, 20, 24, 28)


def wide_program(functions: int, branch_free: bool = False) -> str:
    """Concatenate real task references, renaming each copy's solve() uniquely.

    Every reference is one `@solve(...)` function, so the result is a realistic,
    valid program whose size grows linearly with `functions`.
    """
    references = [path.read_text(encoding="utf-8").strip()
                  for path in sorted((ROOT / "zakbench/tasks").glob("*/reference.zak"))]
    if branch_free:
        # zakc rejects programs with more than 128 `?` markers in total, so this
        # series uses only the references without conditionals or ternaries.
        references = [source for source in references if "?" not in source]
    parts = []
    for index in range(functions):
        source = references[index % len(references)]
        parts.append(re.sub(r"\bsolve\(", f"solve_{index}(", source))
    return "".join(parts)


def nested_program(depth: int) -> str:
    """A function whose body nests `depth` alternating loops and conditionals."""
    opening, closing = [], []
    for level in range(depth):
        if level % 2 == 0:
            opening.append(f"~i{level}:0..n{{")
        else:
            opening.append(f"?i{level - 1}%2==0{{t+=i{level - 1};")
        closing.append("}")
    return "@f(n:I)I{t:=0;" + "".join(opening) + "t+=1" + "".join(closing) + "^t}out(f(3))"


def scaling_worker(implementation: str, shape: str, size: int) -> None:
    source = (nested_program(size) if shape == "nesting"
              else wide_program(size, branch_free=shape == "width_branch_free"))
    pipeline = make_pipeline(implementation)
    rss_before = rss_kib()
    assert pipeline(source), (implementation, shape, size)
    samples = []
    budget = time.perf_counter() + 1.0
    while len(samples) < 3 or (time.perf_counter() < budget and len(samples) < 200):
        tick = time.perf_counter()
        pipeline(source)
        samples.append(time.perf_counter() - tick)
    print(json.dumps({"implementation": implementation, "shape": shape, "size": size,
                      "bytes": len(source.encode("utf-8")), "samples": len(samples),
                      "median_ms": statistics.median(samples) * 1e3, "min_ms": min(samples) * 1e3,
                      "rss_before_kib": rss_before,
                      "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}))


def scaling_driver(output: Path) -> None:
    rows = []
    too_slow: set[tuple[str, str]] = set()
    for shape, sizes in (("width", WIDTH_FUNCTIONS), ("width_branch_free", WIDTH_FUNCTIONS),
                         ("nesting", NESTING_DEPTHS)):
        for size in sizes:
            for implementation in IMPLEMENTATIONS:
                if (implementation, shape) in too_slow:
                    # Larger inputs would take minutes; the trend is already established.
                    rows.append({"implementation": implementation, "shape": shape, "size": size,
                                 "skipped": "previous size exceeded 1.5 s per compile"})
                    continue
                command = [sys.executable, str(Path(__file__).resolve()), "--scaling-worker", implementation,
                           "--shape", shape, "--size", str(size)]
                try:
                    stdout, counters = run(command, perf=True)
                    row = json.loads(stdout)
                    row["instructions"] = counters.get("instructions")
                except RuntimeError as error:
                    row = {"implementation": implementation, "shape": shape, "size": size,
                           "error": str(error).strip().splitlines()[-1][:300]}
                if row.get("error") or row.get("median_ms", 0) > 1500:
                    too_slow.add((implementation, shape))
                rows.append(row)
                print(json.dumps({key: row.get(key) for key in
                                  ("implementation", "shape", "size", "bytes", "median_ms", "max_rss_kib", "error")}),
                      flush=True)
    output.write_text(json.dumps({"environment": environment(), "rows": rows}, indent=2) + "\n", encoding="utf-8")


def environment() -> dict:
    cpu = next((line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), "unknown")
    revision = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=False).stdout.strip()
    rustc = subprocess.run(["rustc", "--version"], capture_output=True, text=True, check=False).stdout.strip()
    perf = subprocess.run([perf_binary(), "--version"], capture_output=True, text=True,
                          check=False).stdout.strip() if perf_binary() else None
    profile = re.search(r"\[profile\.release\](.*?)(?:\n\[|\Z)", (ROOT / "zakc/Cargo.toml").read_text(), re.S)
    return {"cargo_release_profile": " ".join(line.strip() for line in (profile.group(1) if profile else "default").splitlines()
                                              if line.strip() and not line.strip().startswith("#")),
            "cpu": cpu, "pinned_cpu": CPU, "kernel": platform.release(), "python": platform.python_version(),
            "rustc": rustc, "perf": perf, "git": revision,
            "valid_programs": len(valid_sources()), "invalid_programs": len(invalid_sources())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=IMPLEMENTATIONS)
    parser.add_argument("--corpus", choices=("valid", "invalid"), default="valid")
    parser.add_argument("--mode", choices=("throughput", "latency", "tracemalloc"), default="throughput")
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--legacy-rounds", type=int, default=20)
    parser.add_argument("--rust-rounds", type=int, default=500)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("results.json"))
    parser.add_argument("--scaling", action="store_true", help="run the size/nesting scaling series")
    parser.add_argument("--scaling-worker", choices=IMPLEMENTATIONS)
    parser.add_argument("--shape", choices=("width", "width_branch_free", "nesting"), default="width")
    parser.add_argument("--size", type=int, default=1)
    options = parser.parse_args()
    if options.scaling_worker:
        scaling_worker(options.scaling_worker, options.shape, options.size)
    elif options.scaling:
        scaling_driver(options.out)
    elif options.worker:
        worker(options.worker, options.corpus, options.rounds, options.mode)
    else:
        driver(options.out, options.legacy_rounds, options.rust_rounds)


if __name__ == "__main__":
    main()
