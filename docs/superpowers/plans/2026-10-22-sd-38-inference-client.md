# SD-38 Inference Client Implementation Plan

**Goal:** `generate()` returns model text with the server's exact token counts.

**Spec:** `docs/superpowers/specs/2026-10-22-sd-38-inference-client-design.md`

**Stack:** Python 3.12+, stdlib only (`urllib.request`, `json`, `http.server` for tests).

## Constraints

- Token counts come only from the server's `usage`. They are never estimated.
- No hardcoded URL; `GPU_API_URL` is read per call.
- No new dependencies. No retries, streaming, or async.
- Commits start with `SD-38`. No co-author trailers.

### Task 1: Package skeleton and failing tests

**Files:**
- Create `zakbench/__init__.py`, `zakbench/runners/__init__.py`, `zakbench/tests/__init__.py`.
- Create `zakbench/tests/test_inference.py`.

- [x] Write the 7 tests from the spec against a threaded fake server.
- [x] Run `python -m unittest discover -s zakbench/tests -t .` and expect an import failure.

### Task 2: Client

**Files:** Create `zakbench/runners/inference.py`.

- [x] Add `InferenceError`, `InferenceTimeout` and `Generation`.
- [x] Add `generate()`: build the body, POST with `timeout=timeout_s`, and time the call.
- [x] Map errors:
  - `TimeoutError` and `URLError(reason=TimeoutError)` become `InferenceTimeout`.
  - `HTTPError` becomes `InferenceError("HTTP <code>")`.
  - Any other `URLError`, `OSError` or `ValueError` becomes `InferenceError`.
- [x] Validate `choices[0].message.content` (str) and `usage.prompt_tokens`/`completion_tokens` (int).
- [x] Add a `__main__` determinism check: send one prompt twice and print both results and `identical: true/false`.
- [x] Run the tests; all pass.
- [x] Commit `SD-38: Add llama-server inference client with exact token counts`.

### Task 3: Docs

**Files:** Modify `zakbench/runners/README.md`.

- [x] Document `generate()`, the errors, `GPU_API_URL`, the test command and the determinism check.
- [x] Commit `SD-38: Document the inference client`.

### Task 4: PR

- [ ] Run `python3 .github/scripts/check_pr_naming.py <branch> origin/main HEAD`.
- [ ] Push and open the PR. The body says what changed and how it was tested, and notes that the real-server determinism output is **pending until run with `GPU_API_URL`**.
- [ ] Move SD-38 to In Review only after the determinism output is in the PR. Until then, leave it In Progress.

## Verification

- Unit tests pass locally.
- `python -m zakbench.runners.inference "..."` against the real server prints `identical: true` (run by Zakaria; needs Tailscale access to the GPU).
