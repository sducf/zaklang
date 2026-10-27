# Zakc test migration implementation plan

> **For agentic workers:** Use the independent test domains below, then integrate and verify the complete suite.

**Goal:** Move the compiler test suite and fixtures into `zakc`, exercise the actual Rust AST/checker/transpiler, and document every test command.

**Architecture:** Native Cargo integration tests own AST structure, type metadata, semantics, diagnostics, CLI behavior, and source snapshots. Python tests use the PyO3 module for runtime behavior, trusted corpus subprocesses, and Docker conformance. Existing Python compiler consumers remain compatible.

**Tech stack:** Rust, Cargo, PyO3, pytest, Pyright, Docker.

**Spec:** User requests in this session: migrate compiler tests into zakc, document all test commands, and fix the throughput example's missing-libpython link failure.

## Constraints and review focus

- Preserve all legacy language cases and exact runtime stdout expectations.
- Test Rust-owned AST/type metadata directly; do not substitute tests of the legacy Python compiler.
- Default Cargo builds, tests, CLI, and throughput must work without Python development libraries. Python bindings require an explicit `python` feature.
- Move fixtures and update every active consumer; historical design documents retain their original paths.
- Discover benchmark references and pair them with task metadata; eliminate stale assumptions that only ten references exist.
- Docker conformance must fail clearly when Docker/image is unavailable; no silent skips or host-execution fallback.
- Preserve existing uncommitted user changes; apply only reviewed edits after detecting concurrent modifications.

## Task 1: Native test ports

- [x] Port parser/AST and analysis contracts into `zakc/tests/ast.rs` and `analysis.rs`.
- [x] Port every semantic/public-check case and CLI contract into native integration tests.
- [x] Port transpiler AST, deterministic output, diagnostics, and snapshots; retain all 22 trusted runtime examples through the bindings.
- [x] Verify each test domain with targeted Cargo/pytest commands.

## Task 2: Fixtures, build separation, and harnesses

- [x] Reproduce the throughput link failure, then feature-gate PyO3 behind `python`.
- [x] Relocate conformance fixtures, snapshots, corpus tests, and Docker tests; replace Lark-only fixture checks with native AST coverage/signature tests.
- [x] Update Cargo corpus paths, throughput/benchmark/comparison scripts, and active README links.
- [x] Remove superseded compiler test files after preserving their relevant contracts.

## Task 3: Verification and instructions

- [x] Document setup, all native tests, Python extension build, Python tests, Docker conformance, type checking, and formatting/Clippy.
- [x] Run Cargo tests, the throughput example, all local Python tests, Pyright, and Clippy.
- [x] Attempt Docker checks and report an unavailable runtime explicitly.
- [x] Review the integrated diff and apply the verified patch without committing or pushing.

## Progress and rulings

- The optional scope question has not expanded authorization to migrating backend or sandbox compilation callers; this work moves compiler tests and fixtures.
- The two tests monkeypatching the old Python parser's internal exceptions have no Rust callback equivalent; native compiler diagnostics and non-executing check contracts replace that Python-specific implementation coverage.

- Verification: 49 native tests pass; 158 Python tests plus four subtests pass. Full pytest attempts all 177 tests: the 19 Docker tests fail because Docker is unavailable in this WSL distro.
- Pyright, native Clippy, Python-feature library Clippy, formatting, throughput (65 programs), and compiler parity (107 sources, 15 fixtures, 50 references) pass.
- Feature-gating regression found and fixed: PyO3 does not expand a conditional field getter attribute; an explicitly gated `pymethods` getter preserves the read-only Python property.
- Independent review found no further important issues. Benchmark-reference checks use task discovery rather than a fixed count.
