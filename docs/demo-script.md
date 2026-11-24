# Production Dry Run (Phase 3 Prototype)

This checklist confirms that the deployed prototype at https://zaklang.com covers the PRD 3.2 prototype scope end to end: pick a task, generate Zak, compile, transpile and run hidden tests in the Playground, then compare Zak and Python with token totals in the Explorer. Run it after any deploy that touches the backend, the worker or the GPU server.

Total time: about 10 minutes.

## Before you start

- [ ] The GPU pod and llama.cpp are up. If not, use the fallback at the end.
- [ ] https://zaklang.com loads and `GET /tasks` on the backend returns the task list.
- [ ] One browser window signed in as a **member** or **admin**.
- [ ] A second window (private window or another browser) signed in as a **viewer**.

## Accounts

| Account | Role | Used for |
|---|---|---|
| A team account | `member` or `admin` | Matched pair (step 3) |
| A viewer test account | `viewer` | Playground run (step 2) and the 403 check (step 4) |

New signups are `viewer` by default (SD-85). Team accounts are promoted by hand.

## 1. Suite summary

| Step | Action | Expected result |
|---|---|---|
| 1.1 | Open **Explorer**, then **Suites**, and pick suite **9** | Summary for `dev-20261117T170500985216Z`, seed 0, prompt 1, spec 0.1, up to 3 attempts |
| 1.2 | Check the headline numbers | Python 47/50 and Zak 6/50 runs passed. pass@1 84.0% vs 8.0%. pass@3 94.0% vs 12.0%. Zak/Python tokens **8.46x** over the 6 tasks both solved. Correctness gap -82.0 pts |
| 1.3 | Scroll to **Tasks** | 50 rows, each with a Zak and Python outcome. No hidden test inputs or expected outputs anywhere |

Source of truth: `zakbench/reports/dev-baseline-v0.1.md`.

## 2. Playground run

Task: **Frequency Count** (`frequency_count`). Zak and Python both solve it in suite 9.

| Step | Action | Expected result |
|---|---|---|
| 2.1 | Open **Playground**, pick **Frequency Count**, keep the default model, pick **Zak** | Task statement with `items: string[]` and returns `map<string, integer>`. No hidden tests shown |
| 2.2 | Leave the editor empty and press **Generate & run**. Start a timer | Status goes to running, with a queue position while queued |
| 2.3 | Wait for the result | Generated Zak in `solution.zak`, Compile shows "Zak to Python, no errors", Python in `transpiled.py`, Run shows 5 of 5 passed |
| 2.4 | Read the result panel | Status **Passed**, 1 attempt, **919** total tokens (880 prompt, 39 completion) |

Pass condition: under 60 seconds from Generate & run to Passed (PRD F8), and the token count matches suite 9.

Optional: delete the return type from the Zak and press **Compile**. The error shows line, column, code and message, the same format the model gets in a repair attempt.

## 3. Matched pair

| Step | Action | Expected result |
|---|---|---|
| 3.1 | As the team account, open **Explorer**, pick **Frequency Count** next to **Run matched**, press it | The pair page opens with a Zak run and a Python run, same model and seed |
| 3.2 | Wait for both runs | Both **Passed**. Zak **919** tokens (880 + 39), Python **156** tokens (103 + 53), shown side by side with the Zak minus Python table |

These match the suite 9 numbers for this task (ratio 5.89x).

## 4. Viewer limits

| Step | Action | Expected result |
|---|---|---|
| 4.1 | As the viewer, open **Explorer**, pick any task, press **Run matched** | Red alert "Member or admin role required to launch matched runs". No runs are created |

Other limits from SD-85 to keep in mind: viewers get 20 Playground runs a day, the site allows 200 API runs a day in total, the queue caps at 50 queued runs, and login and signup allow 10 requests per minute per IP. All return 429 with a message when hit.

## Fallback if the GPU is down

Do not start new runs. Everything below is already stored.

1. Step 1 needs no GPU.
2. Open a stored Playground run at `/explorer/runs?run=<id>` (for example run 258, `frequency_count` Zak, passed, 919 tokens).
3. Open a stored pair at `/explorer/pairs/<pair_id>` and check step 3 against it.
4. Step 4 still works, since the role check happens before anything is queued.

Hand-written runs return "Hand-written runs are paused while the GPU is offline" while the GPU is down. **Compile** still works, since it does not create a run.

## Last dry run: Nov 24, 2026

| Check | Result |
|---|---|
| Suite 9 summary | Matches `dev-baseline-v0.1.md` exactly |
| Playground, `frequency_count` Zak (run 258) | Passed in 12 s, 919 tokens |
| Matched pair, `frequency_count` (runs 262, 263) | Both passed, Zak 919, Python 156 |
| Viewer Run matched | 403 alert shown, no runs created |
| Hidden tests on any screen | None |

Issues found and filed: Zak generations for `array_sum`, `count_evens` and `count_vowels` no longer match suite 9 (SD-87), suite 8 stuck as running (SD-88), and Zak runs that never compile show "error" instead of "failed" (SD-89). Until SD-87 is fixed, use `frequency_count` for this check.
