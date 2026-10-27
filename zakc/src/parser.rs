//! Native PEG parsing. The Python compiler is never invoked here.
use crate::{
    ast::*,
    error::{CompilerError, ErrorCode, ErrorContext},
};
use pest::{
    Parser,
    iterators::{Pair, Pairs},
};
use pest_derive::Parser;

#[derive(Parser)]
#[grammar = "zak.pest"]
struct ZakParser;
type Result<T> = std::result::Result<T, CompilerError>;
type P<'a> = Pair<'a, Rule>;

fn span(pair: &P<'_>) -> Span {
    let range = pair.as_span();
    let (line, col) = range.start_pos().line_col();
    let (end_line, end_col) = range.end_pos().line_col();
    Span {
        start: range.start(),
        end: range.end(),
        line,
        col,
        end_line,
        end_col,
    }
}
fn next<'a>(pairs: &mut Pairs<'a, Rule>, location: Span) -> Result<P<'a>> {
    pairs
        .next()
        .trace_ctx("expected grammar child")
        .at(location)
}

pub fn parse(source: &str) -> Result<Program> {
    crate::with_stack(|| parse_inner(source))
}

fn parse_inner(source: &str) -> Result<Program> {
    guard_complexity(source)?;
    let mut pairs = ZakParser::parse(Rule::program, source).map_err(|error| {
        let location = match error.location {
            pest::error::InputLocation::Pos(offset) => Span::at_offset(source, offset),
            pest::error::InputLocation::Span((start, end)) => {
                Span::at_offset(source, start).through(Span::at_offset(source, end))
            }
        };
        CompilerError::new(ErrorCode::SyntaxError, Some(location), error.to_string())
    })?;
    let program = next(&mut pairs, Span::point(1, 1))?;
    let seq = next(&mut program.into_inner(), Span::point(1, 1))?;
    Ok(Program {
        statements: Builder { next_id: 0 }.block(seq)?,
    })
}

fn guard_complexity(source: &str) -> Result<()> {
    if source.len() > 1_000_000 {
        return Err(CompilerError::new(
            ErrorCode::ComplexityLimit,
            Some(Span::at_offset(source, 1_000_000)),
            "Source exceeds the 1 MB prototype budget",
        ));
    }
    let mut in_string = false;
    let mut escaped = false;
    let mut nesting = 0usize;
    let mut unary_run = 0usize;
    let mut branches = 0usize;
    for (offset, ch) in source.char_indices() {
        if in_string {
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
            }
        } else {
            match ch {
                '"' => in_string = true,
                '(' | '[' | '{' => nesting += 1,
                ')' | ']' | '}' => nesting = nesting.saturating_sub(1),
                _ => (),
            }
            if matches!(ch, '-' | '#' | '!') {
                unary_run += 1;
            } else if !ch.is_whitespace() {
                unary_run = 0;
            }
            // Ternaries and elif chains recurse without adding delimiters.
            // Bound their total markers before Pest builds recursive frames.
            if ch == '?' {
                branches += 1;
            }
            if nesting > 32 || unary_run > 128 || branches > 128 {
                return Err(CompilerError::new(
                    ErrorCode::ComplexityLimit,
                    Some(Span::at_offset(source, offset)),
                    "Prototype source/nesting budget exceeded",
                ));
            }
        }
    }
    Ok(())
}

struct Builder {
    next_id: u32,
}
impl Builder {
    fn id(&mut self) -> NodeId {
        let id = NodeId(self.next_id);
        self.next_id += 1;
        id
    }
    fn expr_node(&mut self, location: Span, kind: ExprKind) -> Result<Expr> {
        let child_depth = match &kind {
            ExprKind::Literal(_) | ExprKind::Name(_) => 0,
            ExprKind::Array(items) => items.iter().map(|e| e.depth).max().unwrap_or(0),
            ExprKind::Map(items) => items
                .iter()
                .flat_map(|(k, v)| [k.depth, v.depth])
                .max()
                .unwrap_or(0),
            ExprKind::Unary(_, e) | ExprKind::Cast(_, e) => e.depth,
            ExprKind::Binary(a, _, b) | ExprKind::Index(a, b) => a.depth.max(b.depth),
            ExprKind::Call { arguments, .. } => {
                arguments.iter().map(|e| e.depth).max().unwrap_or(0)
            }
            ExprKind::Conditional {
                condition,
                then_value,
                else_value,
            } => condition.depth.max(then_value.depth).max(else_value.depth),
            ExprKind::Slice {
                collection,
                lower,
                upper,
            } => collection
                .depth
                .max(lower.as_ref().map_or(0, |e| e.depth))
                .max(upper.as_ref().map_or(0, |e| e.depth)),
            ExprKind::Comprehension {
                value,
                iteration,
                condition,
                ..
            } => value
                .depth
                .max(iteration.start.depth)
                .max(iteration.stop.as_ref().map_or(0, |e| e.depth))
                .max(condition.as_ref().map_or(0, |e| e.depth)),
        };
        if child_depth >= 128 {
            return Err(CompilerError::new(
                ErrorCode::ComplexityLimit,
                Some(location),
                "Expression nesting exceeds 128",
            ));
        }
        Ok(Expr {
            id: self.id(),
            span: location,
            kind,
            depth: child_depth + 1,
        })
    }
    fn binding(&mut self, pair: P<'_>) -> BindingName {
        BindingName {
            id: self.id(),
            name: pair.as_str().to_owned(),
            span: span(&pair),
        }
    }
    fn block(&mut self, pair: P<'_>) -> Result<Vec<Stmt>> {
        if pair.as_rule() == Rule::block {
            return self.block(next(&mut pair.into_inner(), Span::point(1, 1))?);
        }
        pair.into_inner().map(|pair| self.statement(pair)).collect()
    }
    fn ty(pair: P<'_>) -> Result<Type> {
        let location = span(&pair);
        let kind = pair.as_rule();
        let text = pair.as_str();
        let mut children = pair.clone().into_inner();
        Ok(match kind {
            Rule::ty => Self::ty(next(&mut children, location)?)?,
            Rule::primitive => match text {
                "I" => Type::Int,
                "R" => Type::Real,
                "B" => Type::Bool,
                "S" => Type::Str,
                _ => {
                    return Err(CompilerError::new(
                        ErrorCode::InternalError,
                        Some(location),
                        "Unknown primitive",
                    ));
                }
            },
            Rule::array_type => Type::array(Self::ty(next(&mut children, location)?)?),
            Rule::map_type => Type::map(
                Self::ty(next(&mut children, location)?)?,
                Self::ty(next(&mut children, location)?)?,
            ),
            _ => {
                return Err(CompilerError::new(
                    ErrorCode::InternalError,
                    Some(location),
                    "Expected a type",
                ));
            }
        })
    }
    fn statement(&mut self, pair: P<'_>) -> Result<Stmt> {
        let location = span(&pair);
        let rule = pair.as_rule();
        if rule == Rule::call {
            let expression = self.expression(pair)?;
            return Ok(Stmt {
                id: self.id(),
                span: location,
                kind: StmtKind::Call(expression),
            });
        }
        let mut children = pair.into_inner();
        let kind = match rule {
            Rule::declare => {
                let name = next(&mut children, location)?.as_str().to_owned();
                let value_or_type = next(&mut children, location)?;
                let (declared_type, value) = if value_or_type.as_rule() == Rule::ty {
                    (
                        Some(Self::ty(value_or_type)?),
                        self.expression(next(&mut children, location)?)?,
                    )
                } else {
                    (None, self.expression(value_or_type)?)
                };
                StmtKind::Declare {
                    name,
                    declared_type,
                    value,
                }
            }
            Rule::assign => {
                let target = self.expression(next(&mut children, location)?)?;
                let op = next(&mut children, location)?;
                let operator = if op.as_str() == "=" {
                    AssignOp::Set
                } else {
                    AssignOp::Augmented(Self::binary(&op.as_str()[..1], location)?)
                };
                StmtKind::Assign {
                    target,
                    operator,
                    value: self.expression(next(&mut children, location)?)?,
                }
            }
            Rule::append => StmtKind::Append {
                target: self.expression(next(&mut children, location)?)?,
                value: self.expression(next(&mut children, location)?)?,
            },
            Rule::return_stmt => StmtKind::Return(self.expression(next(&mut children, location)?)?),
            Rule::break_stmt => StmtKind::Break,
            Rule::continue_stmt => StmtKind::Continue,
            Rule::if_stmt => {
                let condition = self.expression(next(&mut children, location)?)?;
                let then_body = self.block(next(&mut children, location)?)?;
                let else_body = match children.next() {
                    None => vec![],
                    Some(branch) if branch.as_rule() == Rule::block => self.block(branch)?,
                    Some(branch) => vec![self.statement(branch)?],
                };
                StmtKind::If {
                    condition,
                    then_body,
                    else_body,
                }
            }
            Rule::while_stmt => StmtKind::While {
                condition: self.expression(next(&mut children, location)?)?,
                body: self.block(next(&mut children, location)?)?,
            },
            Rule::for_stmt => {
                let names = next(&mut children, location)?
                    .into_inner()
                    .map(|p| self.binding(p))
                    .collect();
                let iteration = self.iteration(next(&mut children, location)?)?;
                StmtKind::For {
                    names,
                    iteration,
                    body: self.block(next(&mut children, location)?)?,
                }
            }
            Rule::function => {
                let name = next(&mut children, location)?.as_str().to_owned();
                let parameters_or_type = next(&mut children, location)?;
                let mut parameters = vec![];
                let return_type = if parameters_or_type.as_rule() == Rule::params {
                    for param in parameters_or_type.into_inner() {
                        let mut fields = param.into_inner();
                        let binding = self.binding(next(&mut fields, location)?);
                        parameters.push(Parameter {
                            binding,
                            ty: Self::ty(next(&mut fields, location)?)?,
                        });
                    }
                    Self::ty(next(&mut children, location)?)?
                } else {
                    Self::ty(parameters_or_type)?
                };
                StmtKind::Function(Function {
                    name,
                    parameters,
                    return_type,
                    body: self.block(next(&mut children, location)?)?,
                })
            }
            _ => {
                return Err(CompilerError::new(
                    ErrorCode::InternalError,
                    Some(location),
                    format!("Unexpected statement {rule:?}"),
                ));
            }
        };
        Ok(Stmt {
            id: self.id(),
            span: location,
            kind,
        })
    }
    fn iteration(&mut self, pair: P<'_>) -> Result<Iteration> {
        let location = span(&pair);
        let mut children = pair.into_inner();
        let start = self.expression(next(&mut children, location)?)?;
        let stop = children.next().map(|p| self.expression(p)).transpose()?;
        Ok(Iteration {
            span: location,
            start,
            stop,
        })
    }
    fn binary(text: &str, location: Span) -> Result<BinaryOp> {
        text.parse().map_err(|_| {
            CompilerError::new(
                ErrorCode::InternalError,
                Some(location),
                "Unknown binary operator",
            )
        })
    }

    fn expression(&mut self, pair: P<'_>) -> Result<Expr> {
        let location = span(&pair);
        let rule = pair.as_rule();
        let text = pair.as_str();
        let mut children = pair.clone().into_inner();
        let kind = match rule {
            Rule::expr | Rule::parenthesized | Rule::lower | Rule::upper => {
                return self.expression(next(&mut children, location)?);
            }
            Rule::integer => ExprKind::Literal(Literal::Int(text.to_owned())),
            Rule::float => ExprKind::Literal(Literal::Real(text.to_owned())),
            Rule::boolean => ExprKind::Literal(Literal::Bool(text == "T")),
            Rule::string => {
                ExprKind::Literal(Literal::Str(serde_json::from_str(text).at(location)?))
            }
            Rule::name => ExprKind::Name(text.to_owned()),
            Rule::array => {
                let items: Vec<_> = children.collect();
                match items.as_slice() {
                    [value, tail] if tail.as_rule() == Rule::comprehension => {
                        let value = Box::new(self.expression(value.clone())?);
                        let mut fields = tail.clone().into_inner();
                        let name = next(&mut fields, location)?.as_str().to_owned();
                        let iteration = Box::new(self.iteration(next(&mut fields, location)?)?);
                        let condition = fields
                            .next()
                            .map(|p| self.expression(p).map(Box::new))
                            .transpose()?;
                        ExprKind::Comprehension {
                            value,
                            name,
                            iteration,
                            condition,
                        }
                    }
                    _ => ExprKind::Array(
                        items
                            .into_iter()
                            .map(|p| self.expression(p))
                            .collect::<Result<_>>()?,
                    ),
                }
            }
            Rule::map => {
                let mut entries = vec![];
                for pair in children {
                    let mut fields = pair.into_inner();
                    entries.push((
                        self.expression(next(&mut fields, location)?)?,
                        self.expression(next(&mut fields, location)?)?,
                    ));
                }
                ExprKind::Map(entries)
            }
            Rule::cast => ExprKind::Cast(
                Self::ty(next(&mut children, location)?)?,
                Box::new(self.expression(next(&mut children, location)?)?),
            ),
            Rule::call => {
                let name = next(&mut children, location)?.as_str().to_owned();
                let arguments = match children.next() {
                    Some(args) => args
                        .into_inner()
                        .map(|p| self.expression(p))
                        .collect::<Result<_>>()?,
                    None => vec![],
                };
                ExprKind::Call { name, arguments }
            }
            Rule::ternary => {
                let condition = self.expression(next(&mut children, location)?)?;
                let Some(then_value) = children.next() else {
                    return Ok(condition);
                };
                ExprKind::Conditional {
                    condition: Box::new(condition),
                    then_value: Box::new(self.expression(then_value)?),
                    else_value: Box::new(self.expression(next(&mut children, location)?)?),
                }
            }
            Rule::or_expr | Rule::and_expr | Rule::compare | Rule::sum | Rule::product => {
                let mut value = self.expression(next(&mut children, location)?)?;
                while let Some(op) = children.next() {
                    let right = self.expression(next(&mut children, location)?)?;
                    let span = value.span.through(right.span);
                    value = self.expr_node(
                        span,
                        ExprKind::Binary(
                            Box::new(value),
                            Self::binary(op.as_str(), span)?,
                            Box::new(right),
                        ),
                    )?;
                }
                return Ok(value);
            }
            Rule::not_expr | Rule::unary => {
                let mut fields: Vec<_> = children.collect();
                let last = fields
                    .pop()
                    .trace_ctx("missing unary operand")
                    .at(location)?;
                let mut value = self.expression(last)?;
                for prefix in fields.into_iter().rev() {
                    let op = match prefix.as_str() {
                        "!" => UnaryOp::Not,
                        "#" => UnaryOp::Len,
                        _ => UnaryOp::Neg,
                    };
                    value = self.expr_node(
                        span(&prefix).through(value.span),
                        ExprKind::Unary(op, Box::new(value)),
                    )?;
                }
                return Ok(value);
            }
            Rule::post | Rule::target => {
                let mut value = self.expression(next(&mut children, location)?)?;
                for suffix in children {
                    let span = value.span.through(span(&suffix));
                    let suffix_rule = suffix.as_rule();
                    let mut fields = suffix.into_inner();
                    let kind = if suffix_rule == Rule::index_suffix {
                        ExprKind::Index(
                            Box::new(value),
                            Box::new(self.expression(next(&mut fields, span)?)?),
                        )
                    } else {
                        let (mut lower, mut upper, mut colon) = (None, None, false);
                        for bound in fields {
                            match bound.as_rule() {
                                Rule::lower => lower = Some(Box::new(self.expression(bound)?)),
                                Rule::upper => upper = Some(Box::new(self.expression(bound)?)),
                                Rule::colon => colon = true,
                                _ => (),
                            }
                        }
                        if !colon {
                            let index = lower.trace_ctx("missing index").at(span)?;
                            value =
                                self.expr_node(span, ExprKind::Index(Box::new(value), index))?;
                            continue;
                        }
                        ExprKind::Slice {
                            collection: Box::new(value),
                            lower,
                            upper,
                        }
                    };
                    value = self.expr_node(span, kind)?;
                }
                return Ok(value);
            }
            _ => {
                return Err(CompilerError::new(
                    ErrorCode::InternalError,
                    Some(location),
                    format!("Unexpected expression {rule:?}"),
                ));
            }
        };
        self.expr_node(location, kind)
    }
}
