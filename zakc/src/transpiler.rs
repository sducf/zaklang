//! Emit standalone Python and parse it into an owned RustPython AST.
use crate::{
    ast::*,
    error::{CompilerError, ErrorCode, ErrorContext},
    semantic::{Builtin, CheckedProgram},
};
use rustpython_parser::{Parse, ast as py};
use serde::Serialize;
use std::collections::BTreeSet;

#[derive(Clone, Debug, Serialize)]
pub struct SourceMapEntry {
    pub python_line: usize,
    pub zak: Span,
}
#[derive(Debug)]
pub struct TranspiledProgram {
    pub source: String,
    pub python_ast: py::Suite,
    pub source_map: Vec<SourceMapEntry>,
}

pub fn transpile(program: &CheckedProgram) -> Result<TranspiledProgram, CompilerError> {
    crate::with_stack(|| transpile_inner(program))
}

fn transpile_inner(program: &CheckedProgram) -> Result<TranspiledProgram, CompilerError> {
    let mut emitter = Emitter {
        checked: program,
        source: String::new(),
        source_map: vec![],
        indent: 0,
        line_number: 1,
    };
    emitter.line("import builtins as _ZAK_builtins", None);
    emitter.line("def _ZAK_join(values, delimiter):", None);
    emitter.line("    return delimiter.join(values)", None);
    for statement in &program.program.statements {
        if matches!(statement.kind, StmtKind::Function(_)) {
            emitter.statement(statement)?;
        }
    }
    for statement in &program.program.statements {
        if !matches!(statement.kind, StmtKind::Function(_)) {
            emitter.statement(statement)?;
        }
    }
    for statement in &program.program.statements {
        if let StmtKind::Function(function) = &statement.kind {
            emitter.line(
                &format!(
                    "_ZAK_builtins.globals()[{}] = {}",
                    quote(&function.name)?,
                    emitter.symbol(statement.id, statement.span)?
                ),
                Some(statement.span),
            );
        }
    }
    let python_ast = py::Suite::parse(&emitter.source, "<zakc-generated>").map_err(|failure| {
        let offset = usize::from(failure.offset);
        let line = emitter.source.as_bytes()[..offset.min(emitter.source.len())]
            .iter()
            .filter(|&&b| b == b'\n')
            .count()
            + 1;
        let span = emitter
            .source_map
            .iter()
            .rev()
            .find(|entry| entry.python_line <= line)
            .map(|entry| entry.zak);
        CompilerError::new(
            ErrorCode::PythonAstError,
            span,
            format!("Invalid emitted Python at generated line {line}: {failure}"),
        )
    })?;
    Ok(TranspiledProgram {
        source: emitter.source,
        python_ast,
        source_map: emitter.source_map,
    })
}

fn quote(text: &str) -> Result<String, CompilerError> {
    serde_json::to_string(text).trace_ctx("encoding a Python string literal")
}
struct Emitter<'a> {
    checked: &'a CheckedProgram,
    source: String,
    source_map: Vec<SourceMapEntry>,
    indent: usize,
    line_number: usize,
}
impl Emitter<'_> {
    fn line(&mut self, text: &str, span: Option<Span>) {
        self.source.push_str(&"    ".repeat(self.indent));
        self.source.push_str(text);
        self.source.push('\n');
        if let Some(zak) = span {
            self.source_map.push(SourceMapEntry {
                python_line: self.line_number,
                zak,
            });
        }
        self.line_number += 1;
    }
    fn symbol(&self, id: NodeId, span: Span) -> Result<&str, CompilerError> {
        self.checked
            .symbols
            .get(&id)
            .map(|s| s.python.as_str())
            .trace_ctx("missing checked symbol during emission")
            .at(span)
    }
    fn ty(&self, node: &Expr) -> Result<&Type, CompilerError> {
        self.checked
            .types
            .get(&node.id)
            .trace_ctx("missing checked expression type during emission")
            .at(node.span)
    }
    fn block(&mut self, statements: &[Stmt], span: Span) -> Result<(), CompilerError> {
        self.indent += 1;
        let result = if statements.is_empty() {
            self.line("pass", Some(span));
            Ok(())
        } else {
            statements.iter().try_for_each(|s| self.statement(s))
        };
        self.indent -= 1;
        result
    }
    fn operator(op: BinaryOp, ty: &Type) -> String {
        match op {
            BinaryOp::Div if *ty == Type::Int => "//".into(),
            BinaryOp::And => "and".into(),
            BinaryOp::Or => "or".into(),
            BinaryOp::In => "in".into(),
            _ => op.to_string(),
        }
    }
    fn statement(&mut self, node: &Stmt) -> Result<(), CompilerError> {
        let span = Some(node.span);
        match &node.kind {
            StmtKind::Declare { value, .. } => self.line(
                &format!(
                    "{} = {}",
                    self.symbol(node.id, node.span)?,
                    self.expression(value)?
                ),
                span,
            ),
            StmtKind::Assign {
                target,
                operator,
                value,
            } => {
                let op = match operator {
                    AssignOp::Set => "=".into(),
                    AssignOp::Augmented(op) => {
                        format!("{}=", Self::operator(*op, self.ty(target)?))
                    }
                };
                self.line(
                    &format!(
                        "{} {op} {}",
                        self.expression(target)?,
                        self.expression(value)?
                    ),
                    span,
                );
            }
            StmtKind::Append { target, value } => self.line(
                &format!(
                    "{}.append({})",
                    self.expression(target)?,
                    self.expression(value)?
                ),
                span,
            ),
            StmtKind::Return(value) => {
                self.line(&format!("return {}", self.expression(value)?), span)
            }
            StmtKind::Break => self.line("break", span),
            StmtKind::Continue => self.line("continue", span),
            StmtKind::Call(call) => self.line(&self.expression(call)?, span),
            StmtKind::If {
                condition,
                then_body,
                else_body,
            } => {
                self.line(&format!("if {}:", self.expression(condition)?), span);
                self.block(then_body, node.span)?;
                if !else_body.is_empty() {
                    self.line("else:", span);
                    self.block(else_body, node.span)?;
                }
            }
            StmtKind::While { condition, body } => {
                self.line(&format!("while {}:", self.expression(condition)?), span);
                self.block(body, node.span)?;
            }
            StmtKind::For {
                names,
                iteration,
                body,
            } => {
                let mut iterable = self.expression(&iteration.start)?;
                if let Some(stop) = &iteration.stop {
                    iterable = format!(
                        "_ZAK_builtins.range({iterable}, {})",
                        self.expression(stop)?
                    );
                } else if names.len() == 2 {
                    iterable = format!("{iterable}.items()");
                }
                let target = names
                    .iter()
                    .map(|name| self.symbol(name.id, name.span))
                    .collect::<Result<Vec<_>, _>>()?
                    .join(", ");
                self.line(&format!("for {target} in {iterable}:"), span);
                self.block(body, node.span)?;
            }
            StmtKind::Function(function) => {
                let args = function
                    .parameters
                    .iter()
                    .map(|p| self.symbol(p.binding.id, p.binding.span))
                    .collect::<Result<Vec<_>, _>>()?
                    .join(", ");
                self.line(
                    &format!("def {}({args}):", self.symbol(node.id, node.span)?),
                    span,
                );
                let mut globals = BTreeSet::new();
                self.global_writes(&function.body, &mut globals)?;
                self.indent += 1;
                if !globals.is_empty() {
                    self.line(
                        &format!(
                            "global {}",
                            globals.into_iter().collect::<Vec<_>>().join(", ")
                        ),
                        span,
                    );
                }
                self.indent -= 1;
                self.block(&function.body, node.span)?;
            }
        }
        Ok(())
    }
    fn global_writes(
        &self,
        statements: &[Stmt],
        globals: &mut BTreeSet<String>,
    ) -> Result<(), CompilerError> {
        for statement in statements {
            match &statement.kind {
                StmtKind::Assign { target, .. } if matches!(target.kind, ExprKind::Name(_)) => {
                    let binding = self
                        .checked
                        .symbols
                        .get(&target.id)
                        .trace_ctx("resolving a global assignment")
                        .at(target.span)?;
                    if binding.module {
                        globals.insert(binding.python.clone());
                    }
                }
                StmtKind::If {
                    then_body,
                    else_body,
                    ..
                } => {
                    self.global_writes(then_body, globals)?;
                    self.global_writes(else_body, globals)?;
                }
                StmtKind::While { body, .. } | StmtKind::For { body, .. } => {
                    self.global_writes(body, globals)?
                }
                _ => (),
            }
        }
        Ok(())
    }
    fn expression(&self, node: &Expr) -> Result<String, CompilerError> {
        Ok(match &node.kind {
            ExprKind::Literal(literal) => match literal {
                // Retain arbitrary-size integer lexemes; do not impose Rust i64 limits on Zak.
                Literal::Int(text) => {
                    let text = text.trim_start_matches('0');
                    if text.is_empty() {
                        "0".into()
                    } else {
                        text.to_owned()
                    }
                }
                Literal::Real(text) => text.clone(),
                Literal::Bool(true) => "True".into(),
                Literal::Bool(false) => "False".into(),
                Literal::Str(text) => quote(text)?,
            },
            ExprKind::Name(_) => self.symbol(node.id, node.span)?.to_owned(),
            ExprKind::Array(items) => format!(
                "[{}]",
                items
                    .iter()
                    .map(|e| self.expression(e))
                    .collect::<Result<Vec<_>, _>>()?
                    .join(", ")
            ),
            ExprKind::Map(entries) => format!(
                "{{{}}}",
                entries
                    .iter()
                    .map(|(k, v)| Ok(format!("{}: {}", self.expression(k)?, self.expression(v)?)))
                    .collect::<Result<Vec<_>, CompilerError>>()?
                    .join(", ")
            ),
            ExprKind::Unary(op, operand) => {
                let value = self.expression(operand)?;
                match op {
                    UnaryOp::Neg => format!("(-{value})"),
                    UnaryOp::Not => format!("(not {value})"),
                    UnaryOp::Len => format!("_ZAK_builtins.len({value})"),
                }
            }
            ExprKind::Binary(left, op, right) => format!(
                "({} {} {})",
                self.expression(left)?,
                Self::operator(*op, self.ty(left)?),
                self.expression(right)?
            ),
            ExprKind::Conditional {
                condition,
                then_value,
                else_value,
            } => format!(
                "({} if {} else {})",
                self.expression(then_value)?,
                self.expression(condition)?,
                self.expression(else_value)?
            ),
            ExprKind::Index(collection, index) => format!(
                "{}[{}]",
                self.expression(collection)?,
                self.expression(index)?
            ),
            ExprKind::Slice {
                collection,
                lower,
                upper,
            } => format!(
                "{}[{}:{}]",
                self.expression(collection)?,
                lower
                    .as_ref()
                    .map(|e| self.expression(e))
                    .transpose()?
                    .unwrap_or_default(),
                upper
                    .as_ref()
                    .map(|e| self.expression(e))
                    .transpose()?
                    .unwrap_or_default()
            ),
            ExprKind::Cast(ty, value) => {
                let name = match ty {
                    Type::Int => "int",
                    Type::Real => "float",
                    Type::Bool => "bool",
                    Type::Str => "str",
                    _ => {
                        return Err(CompilerError::new(
                            ErrorCode::InternalError,
                            Some(node.span),
                            "Non-primitive checked cast",
                        ));
                    }
                };
                format!("_ZAK_builtins.{name}({})", self.expression(value)?)
            }
            ExprKind::Call { name, arguments } => self.call(node, name, arguments)?,
            ExprKind::Comprehension { .. } => {
                return Err(CompilerError::new(
                    ErrorCode::UnsupportedFeature,
                    Some(node.span),
                    "Cannot emit an unchecked comprehension",
                ));
            }
        })
    }
    fn call(&self, node: &Expr, name: &str, arguments: &[Expr]) -> Result<String, CompilerError> {
        let args = arguments
            .iter()
            .map(|e| self.expression(e))
            .collect::<Result<Vec<_>, _>>()?;
        if self.checked.functions.contains_key(name) {
            return Ok(format!(
                "{}({})",
                self.symbol(node.id, node.span)?,
                args.join(", ")
            ));
        }
        let builtin: Builtin = name.parse().map_err(|_| {
            CompilerError::new(
                ErrorCode::InternalError,
                Some(node.span),
                "Unknown checked builtin",
            )
        })?;
        Ok(match builtin {
            Builtin::Out | Builtin::Abs | Builtin::Min | Builtin::Max | Builtin::Srt => {
                let function = match builtin {
                    Builtin::Out => "print".into(),
                    Builtin::Srt => "sorted".into(),
                    _ => builtin.to_string(),
                };
                format!("_ZAK_builtins.{function}({})", args.join(", "))
            }
            Builtin::Sum => {
                let start = if self.ty(&arguments[0])? == &Type::array(Type::Real) {
                    "0.0"
                } else {
                    "0"
                };
                format!("_ZAK_builtins.sum({}, {start})", args[0])
            }
            Builtin::Rev => format!("_ZAK_builtins.list(_ZAK_builtins.reversed({}))", args[0]),
            Builtin::Keys | Builtin::Vals => format!(
                "_ZAK_builtins.list({}.{}())",
                args[0],
                if builtin == Builtin::Keys {
                    "keys"
                } else {
                    "values"
                }
            ),
            Builtin::Pop | Builtin::Del => format!("{}.pop({})", args[0], args[1..].join(", ")),
            Builtin::Spl | Builtin::Up | Builtin::Lo => format!(
                "{}.{}({})",
                args[0],
                match builtin {
                    Builtin::Spl => "split",
                    Builtin::Up => "upper",
                    _ => "lower",
                },
                args[1..].join(", ")
            ),
            Builtin::Jn => format!("_ZAK_join({})", args.join(", ")),
        })
    }
}
