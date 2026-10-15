# tasks/

Benchmark problem definitions and their hidden deterministic tests.

Each task lives in its own folder named after the task id:

```text
tasks/
├── check_references.py
└── array_sum/
    ├── task.json
    ├── hidden_tests.json
    ├── reference.py
    └── reference.zak
```

The dev suite has 10 tasks: `array_sum`, `palindrome`, `frequency_count`,
`binary_search`, `merge_sorted`, `group_totals`, `parse_key_values`,
`balanced_brackets`, `shipping_cost`, and `bank_account`.

`task.json` is the part the model is allowed to see. `hidden_tests.json` is the
part it never sees. They are separate files so a prompt builder can load the
task without any chance of leaking the tests into the prompt.

One task definition is used for both the Zak run and the Python run. Nothing in
`task.json` is language specific, so the same file produces both prompts.

---

## task.json

A single JSON object with these fields. All of them are required.

| Field          | Type            | Meaning                                                        |
| -------------- | --------------- | -------------------------------------------------------------- |
| `id`           | string          | Unique task id. Must match the folder name.                      |
| `title`        | string          | Short human-readable name.                                       |
| `category`     | string          | Grouping label, e.g. `arrays`, `strings`, `maps`.                |
| `prompt`       | string          | The problem statement shown to the model.                        |
| `functionName` | string          | Name of the function the solution must define.                   |
| `inputs`       | array of object | Parameters, in order. Each has a `name` and a `type`.            |
| `outputType`   | string          | Type the function returns.                                       |

Rules:

- `id` is unique across all tasks and matches its folder name.
- `prompt` describes the problem in plain language. It must not contain Python
  or Zak syntax, and it must not contain any test cases.
- `inputs` is ordered. Position in the array is the argument position.
- Each entry in `inputs` has exactly `name` and `type`.
- An input list may be empty (`[]`) if the function takes no arguments.

### Types

Types are written the same way for every language so one definition works for
both Zak and Python.

| Type                | Meaning                        |
| ------------------- | ------------------------------ |
| `integer`           | whole number                    |
| `float`             | decimal number                  |
| `string`            | text                            |
| `boolean`           | true / false                    |
| `<type>[]`          | array of that type              |
| `map<string, integer>` | map with the given key and value types |

Array and map types nest, e.g. `integer[][]` or `map<string, integer[]>`.

### Example

```json
{
  "id": "array_sum",
  "title": "Array Sum",
  "category": "arrays",
  "prompt": "Write a function that returns the sum of all integers in an array.",
  "functionName": "solve",
  "inputs": [
    {
      "name": "nums",
      "type": "integer[]"
    }
  ],
  "outputType": "integer"
}
```

---

## hidden_tests.json

A JSON array of test case objects. Each test case has:

| Field      | Type  | Meaning                                                   |
| ---------- | ----- | --------------------------------------------------------- |
| `inputs`   | array | Arguments to pass, in the same order as `task.json` inputs |
| `expected` | any   | The exact value the function must return                   |

Rules:

- `inputs` has one element per entry in the task's `inputs` array, in the same
  order. A function taking one array argument therefore has a test `inputs` of
  `[[1, 2, 3]]`, not `[1, 2, 3]`.
- `expected` must match `outputType`.
- Tests must be deterministic. No randomness, no current time, no file or
  network access, no reliance on iteration order.
- `expected` is compared by value, so it has to be something that can be
  checked exactly. Avoid floats where an exact comparison would be fragile.
- Include normal cases and edge cases, e.g. empty input.
- These values are never inserted into the prompt.

### Example

```json
[
  {
    "inputs": [[1, 2, 3]],
    "expected": 6
  },
  {
    "inputs": [[-2, 5, 1]],
    "expected": 4
  },
  {
    "inputs": [[]],
    "expected": 0
  }
]
```

---

## Reference solutions

Reference solutions prove a task is solvable. They are never part of a model
prompt.

- `reference.py` is a plain Python solution that defines the function named by
  `functionName`, with parameters in `inputs` order. It uses only the standard
  library. Every task has one (SD-37).
- `reference.zak` is a hand-written Zak solution with the same signature. The
  three sample tasks include these as part of SD-35. Grammar checks live in
  `compiler/tests/conformance`, and SD-34's corpus test runs the transpiled
  references against their hidden tests.

### check_references.py

Run from the repository root:

```sh
python3 zakbench/tasks/check_references.py
```

For every task folder it checks that both JSON files parse, `task.json` has
every field and an `id` matching the folder, `hidden_tests.json` has 5 to 12
cases whose `inputs` match the task's arity, and `reference.py` exists. It then
runs `reference.py` in a fresh, isolated, time-limited Python subprocess and
compares each result to `expected` by value.

It prints one `PASS` or `FAIL` line per task and exits 0 only if every task
passes. Failures name the case number but never print hidden-test values.

---

## Adding a task

1. Make a folder under `tasks/` named after the task id.
2. Write `task.json` with the fields above.
3. Write `hidden_tests.json` with 5 to 12 cases, including at least one edge
   case.
4. Write `reference.py`.
5. Run `python3 zakbench/tasks/check_references.py` and confirm it exits 0.
