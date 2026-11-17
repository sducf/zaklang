# SD-59 — ZakBench Dev Baseline v0.1

**Run date:** November 17, 2026  
**Suite ID:** `dev-20261117T170500985216Z`  
**Status:** Benchmark and reproducibility verification complete

## 1. Experimental Configuration

| Parameter | Value |
|---|---|
| Benchmark suite | `dev` |
| Total tasks | 50 |
| Languages | Python and ZakLang |
| Total evaluations | 100 |
| Reference model | Llama 3.1 8B |
| Inference server | llama.cpp / RunPod |
| Model ID | `llama-3.1-8b` |
| Temperature | 0.0 |
| Random seed | 0 |
| Maximum attempts (K) | 3 |
| Maximum generation tokens | 1,024 |
| Prompt version | 1 |
| Zak specification version | 0.1 |
| Specification token count | Pending SD-54 |
| Database persistence | Enabled (`--persist`) |
| Infrastructure errors | 0 |

The Zak specification token count was not independently measured because SD-54 remains incomplete. No estimated value is substituted.

## 2. Correctness and Token Usage

| Metric | Python | ZakLang |
|---|---:|---:|
| Tasks evaluated | 50 | 50 |
| Tasks solved | 47 | 6 |
| Pass@1 | 84% | 8% |
| Pass@3 | 94% | 12% |
| Total tokens | 15,642 | 168,904 |
| Mean tokens per task | 312.84 | 3,378.08 |
| Median tokens per task | 208.5 | 3,284.5 |
| Repair-token share | 34.61% | 70.12% |
| Truncated attempts | 0 | 9 |
| Runs with truncation | 0 | 5 |
| Infrastructure errors | 0 | 0 |

The full-suite correctness gap (ZakLang minus Python) was **−82 percentage points**.

Across all 50 tasks, ZakLang used approximately **10.80×** as many tokens as Python.

Combined final outcomes were 53 `pass`, 36 `not_run`, 10 `fail`, and 1 `crash`. The crash was a generated-program evaluation outcome for ZakLang's `rotate_array` task, not an infrastructure error.

## 3. Paired Token Analysis

Six tasks were solved successfully by both languages:

`array_sum`, `count_above_threshold`, `count_evens`, `count_vowels`, `frequency_count`, `shipping_cost`.

| Metric | Python | ZakLang |
|---|---:|---:|
| Jointly solved tasks | 6 | 6 |
| Mean total tokens | 152.1667 | 1,287.8333 |
| Median total tokens | 145.0 | 923.5 |

**Paired ZakLang/Python token ratio: 8.4633×**

| Task | ZakLang/Python token ratio |
|---|---:|
| array_sum | 8.2222 |
| count_above_threshold | 6.6763 |
| count_evens | 7.1406 |
| count_vowels | 12.9338 |
| frequency_count | 5.8910 |
| shipping_cost | 9.1991 |

Both languages achieved 100% correctness within this jointly solved subset, so its correctness gap is zero by definition. The meaningful full-suite gap is −82 percentage points.

## 4. Category-Level Results

| Category | Tasks | Python solved | ZakLang solved |
|---|---:|---:|---:|
| algorithms | 2 | 2 | 0 |
| arrays | 7 | 7 | 2 |
| business_rules | 1 | 1 | 1 |
| dynamic_programming | 4 | 4 | 0 |
| maps | 5 | 4 | 2 |
| math | 5 | 5 | 0 |
| parsing | 3 | 2 | 0 |
| simulation | 4 | 3 | 0 |
| sorting_searching | 4 | 4 | 0 |
| stacks_queues | 5 | 5 | 0 |
| strings | 7 | 7 | 1 |
| structured_data | 2 | 2 | 0 |
| validation | 1 | 1 | 0 |
| **Total** | **50** | **47** | **6** |

## 5. Language-Specific Successful Tasks

**Solved by Python only (41):**

`balanced_brackets`, `binary_search`, `climb_stairs`, `clock_minutes`, `coin_change`, `count_inversions`, `count_primes`, `digit_sum`, `edit_distance`, `evaluate_rpn`, `game_of_life_step`, `greatest_common_divisor`, `group_totals`, `integer_sqrt`, `inventory_events`, `is_sorted`, `josephus_survivor`, `leap_year`, `longest_common_prefix`, `longest_unique_substring`, `matrix_transpose`, `max_nesting_depth`, `max_subarray`, `merge_intervals`, `merge_sorted`, `most_frequent_word`, `number_of_islands`, `palindrome`, `parse_key_values`, `remove_adjacent_pairs`, `remove_duplicates`, `reverse_words`, `robot_position`, `roman_to_integer`, `rotate_array`, `run_length_encode`, `running_total`, `simplify_path`, `title_case`, `to_binary`, `two_sum`.

**Solved by ZakLang only:** None.

**Solved by neither language (3):** `bank_account`, `evaluate_expression`, `word_pattern`.

## 6. Reproducibility Verification

Three tasks were rerun in both languages using the original model, seed, prompt/spec versions, temperature, generation limit, and maximum attempt count.

| Task | Language | Original tokens | Rerun tokens | Outcome |
|---|---|---:|---:|---|
| array_sum | ZakLang | 888 | 888 | pass → pass |
| array_sum | Python | 108 | 108 | pass → pass |
| count_evens | ZakLang | 914 | 914 | pass → pass |
| count_evens | Python | 128 | 128 | pass → pass |
| frequency_count | ZakLang | 919 | 919 | pass → pass |
| frequency_count | Python | 156 | 156 | pass → pass |

**Result: All six evaluations reproduced exactly.**

Both final outcomes and token counts matched the baseline. Prompt-token and completion-token totals also matched individually. No reproducibility mismatches were observed.

These checks support repeatability for the three selected tasks; they do not establish exact reproducibility for every task or every future run.

## 7. Database Persistence

The completed suite was stored successfully in Railway PostgreSQL.

| Database verification | Result |
|---|---|
| SuiteRun database ID | 9 |
| Suite status | `completed` |
| Stored benchmark runs | 100 |
| Present in suite-list controller | True |

The saved run data and summary remain under:

`zakbench/results/dev-20261117T170500985216Z/`

Raw benchmark results must remain excluded from Git. Only the baseline report should be committed.

The authenticated HTTP response from `GET /suites` was not separately inspected; the underlying controller and persisted records were verified.

## 8. Interpretation

Under the current Llama 3.1 8B configuration, Python substantially outperformed ZakLang in both program correctness and total token efficiency.

Although ZakLang uses shorter syntax, that advantage did not translate into fewer total model tokens in this experiment. ZakLang required longer prompts containing its language specification and spent a substantially higher proportion of tokens on repair attempts.

The result does not support the hypothesis that shorter syntax automatically improves LLM code-generation efficiency. It establishes a measured baseline for future experiments involving prompt optimization, compiler feedback, task complexity, and model configuration.

## 9. Limitations

The benchmark uses the 50-task development suite and one reference model. It does not establish how other models, prompts, or held-out tasks would perform.

The separately measured Zak specification token count remains pending SD-54. Further prompt/specification changes and additional-model experiments are outside the scope of SD-59.

**Conclusion:** The full matched baseline and the three-task reproducibility check have been completed successfully. The results are preserved for subsequent analysis, regardless of whether the original efficiency hypothesis was supported.