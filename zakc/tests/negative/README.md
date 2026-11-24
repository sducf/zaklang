# Negative Compiler Test Suite

This directory contains invalid Zak programs used to verify structured compiler diagnostics.

## Purpose

The suite supports SD-55 by ensuring that the compiler rejects invalid programs with the expected error code and source location.

## Fixture Structure

Each test case consists of two files:

- `NNN_description.zak` — an intentionally invalid Zak program.
- `NNN_description.error.json` — the expected compiler diagnostic.

Example:

`001_undefined_name.zak`

```zak
x:=1;
out(missing)
```

`001_undefined_name.error.json`

```json
{
  "code": "UNDEFINED_NAME",
  "line": 2,
  "col": 5
}
```

## Error Coverage

The suite covers:

- `SYNTAX_ERROR`
- `UNDEFINED_NAME`
- `TYPE_MISMATCH`
- `CALL_ARITY`
- `DUPLICATE_NAME`
- `MISSING_RETURN`
- `INVALID_CONTROL_FLOW`

## Running the Tests

From the `zakc` directory:

```bash
cargo test --test negative
```

The test runner checks that:

1. At least 30 negative fixtures exist.
2. Each fixture has a corresponding JSON expectation.
3. Every invalid program is rejected.
4. Exactly one diagnostic is produced per fixture.
5. The error code, line, and column match the expectation.
6. The diagnostic contains a nonempty message and source context.

## Adding New Cases

Create a new `.zak` file and a matching `.error.json` file using the same numbered filename prefix. Record the expected error code and source location, then run the test suite.

Expected diagnostics should be reviewed against the language specification rather than accepted solely because the compiler currently produces them.