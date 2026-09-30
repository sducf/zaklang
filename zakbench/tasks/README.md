# tasks/

Benchmark problem definitions and their hidden deterministic tests.

Each task lives in its own folder named after the task id:

```text
tasks/
└── array_sum/
    ├── task.json
    └── hidden_tests.json
```

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

## Adding a task

1. Make a folder under `tasks/` named after the task id.
2. Write `task.json` with the fields above.
3. Write `hidden_tests.json` with at least a couple of normal cases and one
   edge case.
4. Check both files parse as JSON.
