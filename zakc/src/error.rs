//! Source diagnostics plus Rust call-site traces, adapted from SaúdeBridge's ErrorContext.
use crate::ast::Span;
use serde::{Serialize, Serializer};
use std::panic::Location;

#[derive(
    Clone, Copy, Debug, PartialEq, Eq, Serialize, strum::Display, strum::EnumString, strum::EnumIter,
)]
#[strum(serialize_all = "SCREAMING_SNAKE_CASE")]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum ErrorCode {
    InvalidAst,
    SyntaxError,
    InvalidLiteral,
    UndefinedName,
    DuplicateName,
    ReservedName,
    CallArity,
    TypeMismatch,
    InvalidType,
    CannotInferType,
    InvalidTarget,
    InvalidIteration,
    InvalidControlFlow,
    MissingReturn,
    UnsupportedFeature,
    VoidValue,
    ComplexityLimit,
    InternalError,
    IoError,
    PythonAstError,
}

#[derive(Debug, thiserror::Error)]
pub enum ErrorType {
    #[error("{0}")]
    Message(String),
    #[error("File IO: {0}")]
    Io(#[from] std::io::Error),
    #[error("JSON: {0}")]
    Json(#[from] serde_json::Error),
    #[error("Unexpected None::<{0}>")]
    UnexpectedNone(&'static str),
}

#[derive(Clone, Debug, Serialize, derive_more::Display)]
#[display("{file}:{line}:{column}")]
pub struct RustLocation {
    pub file: String,
    pub line: u32,
    pub column: u32,
}

#[derive(Clone, Debug, Serialize)]
pub struct ErrorTrace {
    pub message: Option<String>,
    pub location: RustLocation,
}

impl Default for ErrorTrace {
    #[track_caller]
    fn default() -> Self {
        let caller = Location::caller();

        Self {
            message: None,
            location: RustLocation {
                file: caller.file().to_owned(),
                line: caller.line(),
                column: caller.column(),
            },
        }
    }
}

impl ErrorTrace {
    pub fn message(mut self, message: impl Into<String>) -> Self {
        self.message = Some(message.into());
        self
    }
}

#[derive(Debug, Serialize, thiserror::Error)]
#[cfg_attr(feature = "python", pyo3::pyclass(module = "zakc"))]
#[error("{code}{}: {error}{}", position(.span), trace_text(.sources))]
pub struct CompilerError {
    pub code: ErrorCode,
    /// Location in Zak source, independent of the Rust implementation trace.
    pub span: Option<Span>,
    pub sources: Vec<ErrorTrace>,
    #[serde(serialize_with = "display_error")]
    #[source]
    pub error: ErrorType,
}

fn display_error<S: Serializer>(error: &ErrorType, serializer: S) -> Result<S::Ok, S::Error> {
    serializer.collect_str(error)
}

impl CompilerError {
    #[track_caller]
    pub fn new(code: ErrorCode, span: Option<Span>, message: impl Into<String>) -> Self {
        Self {
            code,
            span,
            sources: vec![ErrorTrace::default()],
            error: ErrorType::Message(message.into()),
        }
    }

    pub fn source(mut self, trace: ErrorTrace) -> Self {
        self.sources.push(trace);
        self
    }

    /// Keep the innermost Zak location when outer stages attach context.
    pub fn at(mut self, span: Span) -> Self {
        self.span.get_or_insert(span);
        self
    }

    pub fn code(mut self, code: ErrorCode) -> Self {
        self.code = code;
        self
    }
}

fn position(span: &Option<Span>) -> String {
    span.map_or_else(String::new, |span| {
        format!(" at {}:{}", span.line, span.col)
    })
}

fn trace_text(sources: &[ErrorTrace]) -> String {
    sources
        .iter()
        .map(|trace| {
            let message = trace
                .message
                .as_ref()
                .map_or_else(String::new, |text| format!(" - {text}"));

            format!("\n  at {}{message}", trace.location)
        })
        .collect()
}

impl From<std::io::Error> for CompilerError {
    #[track_caller]
    fn from(error: std::io::Error) -> Self {
        Self {
            code: ErrorCode::IoError,
            span: None,
            sources: vec![ErrorTrace::default()],
            error: error.into(),
        }
    }
}

impl From<serde_json::Error> for CompilerError {
    #[track_caller]
    fn from(error: serde_json::Error) -> Self {
        Self {
            code: ErrorCode::InvalidLiteral,
            span: None,
            sources: vec![ErrorTrace::default()],
            error: error.into(),
        }
    }
}

pub struct TraceCtx {
    pub message: String,
    pub code: Option<ErrorCode>,
}

impl From<&str> for TraceCtx {
    fn from(message: &str) -> Self {
        Self {
            message: message.to_owned(),
            code: None,
        }
    }
}

impl From<String> for TraceCtx {
    fn from(message: String) -> Self {
        Self {
            message,
            code: None,
        }
    }
}
impl<M: Into<String>> From<(M, ErrorCode)> for TraceCtx {
    fn from((message, code): (M, ErrorCode)) -> Self {
        Self {
            message: message.into(),
            code: Some(code),
        }
    }
}
pub trait ErrorContext<T>: Sized {
    fn trace_at(self, trace: ErrorTrace) -> Result<T, CompilerError>;

    #[track_caller]
    fn trace(self) -> Result<T, CompilerError> {
        self.trace_at(ErrorTrace::default())
    }

    #[track_caller]
    fn trace_ctx(self, context: impl Into<TraceCtx>) -> Result<T, CompilerError> {
        let context = context.into();

        self.trace_at(ErrorTrace::default().message(context.message))
            .map_err(|error| {
                if let Some(code) = context.code {
                    error.code(code)
                } else {
                    error
                }
            })
    }

    #[track_caller]
    fn at(self, span: Span) -> Result<T, CompilerError> {
        self.trace().map_err(|error| error.at(span))
    }
}

impl<T> ErrorContext<T> for Option<T> {
    fn trace_at(self, trace: ErrorTrace) -> Result<T, CompilerError> {
        self.ok_or_else(|| CompilerError {
            code: ErrorCode::InternalError,
            span: None,
            sources: vec![trace],
            error: ErrorType::UnexpectedNone(std::any::type_name::<T>()),
        })
    }
}

impl<T, E: Into<CompilerError>> ErrorContext<T> for Result<T, E> {
    fn trace_at(self, trace: ErrorTrace) -> Result<T, CompilerError> {
        self.map_err(|error| error.into().source(trace))
    }
}
