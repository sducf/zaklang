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

/// Python bindings for checking Zak source and generating Python.
#[cfg(feature = "python")]
#[pyo3::pymodule]
mod zakc {
    use pyo3::{exceptions::PyValueError, prelude::*};

    #[pymodule_export]
    use super::CheckedProgram;

    #[pymodule_export]
    use super::CompilerError;

    #[pymodule_export]
    use super::TranspiledProgram;

    struct PythonErrors(Vec<CompilerError>);

    impl From<PythonErrors> for PyErr {
        fn from(errors: PythonErrors) -> Self {
            PyValueError::new_err(
                errors
                    .0
                    .iter()
                    .map(ToString::to_string)
                    .collect::<Vec<_>>()
                    .join("\n"),
            )
        }
    }

    /// Check Zak source, raising ValueError with diagnostics for invalid programs.
    #[pyfunction]
    fn zak_check(source: &str) -> Result<CheckedProgram, PythonErrors> {
        super::zak_check(source).map_err(PythonErrors)
    }

    /// Generate Python without executing it, raising ValueError on compiler errors.
    #[pyfunction]
    fn zak_transpile(source: &str) -> Result<TranspiledProgram, PythonErrors> {
        super::zak_transpile(source).map_err(PythonErrors)
    }
}
