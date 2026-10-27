//! Scratch implementation: native Zak parsing, checking, and Python emission.
pub mod ast;
pub mod error;
pub mod parser;
pub mod semantic;
pub mod transpiler;

pub use error::{CompilerError, ErrorCode, ErrorContext};
pub use semantic::CheckedProgram;
pub use transpiler::TranspiledProgram;

/// Keep recursive compiler stages usable from small host/runtime thread stacks.
/// Source/AST budgets still reject excessive input rather than growing forever.
pub(crate) fn with_stack<T>(operation: impl FnOnce() -> T) -> T {
    stacker::maybe_grow(2 * 1024 * 1024, 16 * 1024 * 1024, operation)
}

pub fn zak_check(source: &str) -> Result<CheckedProgram, Vec<CompilerError>> {
    with_stack(|| parser::parse(source).map_err(|error| vec![error])?.check())
}

pub fn zak_transpile(source: &str) -> Result<TranspiledProgram, Vec<CompilerError>> {
    with_stack(|| zak_check(source)?.transpile().map_err(|error| vec![error]))
}
