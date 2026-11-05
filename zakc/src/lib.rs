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
    use pyo3::{exceptions::PyValueError, prelude::*, types::PyList};

    #[pymodule_export]
    use super::CheckedProgram;

    #[pymodule_export]
    use super::CompilerError;

    #[pymodule_export]
    use super::TranspiledProgram;

    pyo3::create_exception!(
        zakc,
        ZakCompileError,
        PyValueError,
        "Invalid Zak source; `errors` holds the CompilerError diagnostics."
    );

    #[pymodule_init]
    fn init(module: &Bound<'_, PyModule>) -> PyResult<()> {
        module.add("ZakCompileError", module.py().get_type::<ZakCompileError>())
    }

    /// Raise ZakCompileError with the diagnostics text and structured `errors`.
    fn compile_error(py: Python<'_>, errors: Vec<CompilerError>) -> PyErr {
        let message = errors
            .iter()
            .map(ToString::to_string)
            .collect::<Vec<_>>()
            .join("\n");
        let error = ZakCompileError::new_err(message);
        let attached = errors
            .into_iter()
            .map(|diagnostic| Py::new(py, diagnostic))
            .collect::<PyResult<Vec<_>>>()
            .and_then(|diagnostics| PyList::new(py, diagnostics))
            .and_then(|diagnostics| error.value(py).setattr("errors", diagnostics));

        match attached {
            Ok(()) => error,
            Err(failure) => failure,
        }
    }

    /// Check Zak source, raising ZakCompileError for invalid programs.
    /// The GIL is released while compiling so other Python threads can run.
    #[pyfunction]
    fn zak_check(py: Python<'_>, source: &str) -> PyResult<CheckedProgram> {
        py.detach(|| super::zak_check(source))
            .map_err(|errors| compile_error(py, errors))
    }

    /// Generate Python without executing it, raising ZakCompileError on compiler errors.
    #[pyfunction]
    fn zak_transpile(py: Python<'_>, source: &str) -> PyResult<TranspiledProgram> {
        py.detach(|| super::zak_transpile(source))
            .map_err(|errors| compile_error(py, errors))
    }
}
