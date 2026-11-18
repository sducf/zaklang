# SD-61 — Zak failures in the v0.1 development baseline

This analysis covers all 50 Zak runs in SD-59 suite `dev-20261117T170500985216Z`. The attempt export contains 140 attempts and 168,904 tokens. Six tasks passed, four on their first attempt, matching the [baseline report](dev-baseline-v0.1.md). The tables cover all 134 failed attempts, including the failures before a later pass.

## Compiler diagnostics and next-attempt repair

Each distinct diagnostic code counts once per failed attempt. An attempt can contribute to several code rows. The repair rate is the share of attempts with that code whose immediate next attempt compiled, regardless of test outcome. Attempts with no next attempt are excluded from the rate.

| Code | Failed attempts | Had a next repair | Next repair compiled | Rate |
| --- | ---: | ---: | ---: | ---: |
| SYNTAX_ERROR | 94 | 63 | 3 | 4.8% |
| TYPE_MISMATCH | 10 | 8 | 0 | 0.0% |
| UNDEFINED_NAME | 9 | 7 | 1 | 14.3% |
| CANNOT_INFER_TYPE | 6 | 4 | 0 | 0.0% |
| MISSING_RETURN | 3 | 3 | 0 | 0.0% |
| CALL_ARITY | 1 | 1 | 0 | 0.0% |
| COMPLEXITY_LIMIT | 1 | 0 | 0 | N/A |
| VOID_VALUE | 1 | 1 | 0 | 0.0% |

## Failure causes

Each failed attempt counts once. The classifier gives precedence to timeouts or crashes, then compiled programs with wrong answers. For compilation failures, it checks for syntax diagnostics first, then type diagnostics, then assigns the remaining failures to scope or semantics. This puts `COMPLEXITY_LIMIT`, a compiler budget rejection, in scope or semantics. All three runtime crashes came from `rotate_array`.

| Cause | Failed attempts |
| --- | ---: |
| Syntax | 94 |
| Type | 17 |
| Scope or semantics | 2 |
| Compiled but wrong answer | 18 |
| Timeout or crash | 3 |

## Recurring syntax patterns

Counts here come from manually reading the stored source at the parser’s reported line and column. Each row counts occurrences at the reported failure site. Since parsing stops at the first error, these counts describe what the compiler exposed to the repair loop. The remaining 37 syntax failures had other reported sites.

| Pattern at the reported site | Attempts | Two examples from the export |
| --- | ---: | --- |
| Missing or malformed type in a function signature | 16 | `group_totals #1` starts its body immediately after `amounts:[I])`. `inventory_events #1` uses `map{S:I}` as its return type. |
| Bare statement after an else colon | 12 | `binary_search #1` has `{^i}:^#nums-1`. `coin_change #1` has `{^0}:m:=[]`. |
| Assignment `=` used for comparison | 9 | `max_subarray #1` has `?nums=[]{^0}`. `remove_duplicates #1` has `?m[x]=0`. |
| Unexpected end of source | 8 | `evaluate_rpn #1` ends with `^-tokens[i]}}` while the function body is still open. `robot_position #1` ends with `^#[x,y]` before closing the function body. |
| Single-quoted string literal | 5 | `evaluate_expression #1` uses `expr[i]=='+'`. `max_nesting_depth #1` uses `text[i]=='('`. |
| Dot-method call | 4 | `bank_account #1` uses `m.values()`. `title_case #2` uses `w[i].toUpperCase()`. |
| Declaration operator on an indexed element | 3 | `longest_unique_substring #2` uses `m[c]:=1`. `running_total #2` uses `a[i]:=l`. |

Unexpected end of source describes the parser diagnostic. The export records nine generations that reached the token limit, across five tasks. The two end-of-source examples above both have `finish_reason: stop`.

## Three proposed changes

1. **Supply the exact function header in the task wording for both languages.** Use the task signature to give the model the Zak function name, parameter types, and return type, including the complete header for nested arrays and maps. This follows the baseline fix plan’s suggestion to give both languages equivalent starting information. `group_totals #1–#3` omit the return type, `inventory_events #1–#3` use `map{S:I}`, and `number_of_islands #1–#3` use `[I[]]` where the signature needs `[[I]]`.
2. **Include a source excerpt and a plain-language correction in syntax diagnostics.** At the first rejected token, underline the relevant characters and describe what the parser needs. For `binary_search #1–#3`, replace “expected block or if_stmt” with a hint to wrap the else body in braces. For `remove_duplicates #1–#3`, point at the `=` in the condition and suggest `==`. Both patterns persisted through all three attempts, and only 3 of 63 repairs after a syntax error compiled.
3. **Add one compiler-verified example that builds a collection from scratch.** Show a typed empty array and map (`a:[I]=[]`, `m:{S:I}={}`), appending with `<<`, and updating a map entry with `=`. `evaluate_rpn #3` and `merge_sorted #2` fail on `a:=[]` and `c:=[]`. `run_length_encode #1–#2` fails on `m:={}`. These failed declarations also produced undefined-name diagnostics when later statements used the names.

## Reproduce

From the repository root, run the classifier against the original suite results folder or a folder containing the 50 extracted Zak attempt JSON files.

```sh
python3 -m zakbench.reports.classify_failures path/to/suite-results
```

The classifier prints the two count tables and per-attempt diagnostic evidence. The syntax-pattern review and proposed changes are based on those saved attempts.
