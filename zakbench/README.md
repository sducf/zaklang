# ZakBench

ZakBench is the benchmark used to compare code generated in Zak against code
generated in Python for the same programming task.

The idea is that a model gets the same problem twice, once asked for Zak and
once asked for Python. We then run both solutions against the same hidden tests
and compare correctness and token usage.

This folder only holds benchmark material. It does not contain application or
web UI code.

## Layout

```text
zakbench/
├── tasks/        benchmark problem definitions + hidden tests
├── prompts/      Zak and Python prompt templates sent to the model
├── runners/      code that loads tasks, prompts the model, runs solutions
├── evaluation/   correctness checks, token accounting, timing, metrics
└── results/      output of benchmark runs
```

Each folder has its own README with more detail.
