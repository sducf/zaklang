# tasks/

Benchmark problem definitions and their hidden deterministic tests.

Each task lives in its own folder named after the task id:

```text
tasks/
└── array_sum/
    ├── task.json
    └── hidden_tests.json
```

`task.json` describes the problem, the required function, its inputs and its
output type. `hidden_tests.json` holds the test cases used to check a generated
solution. Hidden tests are kept in a separate file so they are never sent to the
model as part of the prompt.

The exact JSON format is defined in SD-12.
