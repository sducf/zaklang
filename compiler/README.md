# ZakLang Compiler

This directory contains the compiler implementation for ZakLang.

## Structure

- `src/` - Compiler source code
- `tests/` - Compiler tests

## Status

Initial compiler scaffolding is in progress as part of SD-23.

Planned compiler components will be added as the ZakLang language specification and compilation pipeline are defined.

## Conformance fixtures (SD-35)

The [conformance directory](tests/conformance/README.md) contains 15 Zak
programs with expected stdout and grammar validation tests. The three sample
benchmark tasks have `reference.zak` solutions. Install
`compiler/requirements-dev.txt` and run `python -m pytest compiler/tests` from
the repository root to validate these fixtures.

End-to-end conformance and hidden-test execution depend on the parser/AST
(SD-32), transpiler (SD-34), and isolated execution service.
