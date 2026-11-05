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

/// Line starts computed once per parse. Pest's `Position::line_col` rescans
/// the input from offset 0 on every call, which made span construction
/// O(nodes x source length). Lookups here are a binary search plus, only on
/// lines containing non-ASCII text, a character count within that line.
/// Coordinates match pest's: `\n` (including in `\r\n`) ends a line and
/// columns count characters.
struct LineIndex {
    starts: Vec<usize>,
    ascii: Vec<bool>,
}

impl LineIndex {
    fn new(source: &str) -> Self {
        let starts: Vec<usize> = std::iter::once(0)
            .chain(source.match_indices('\n').map(|(offset, _)| offset + 1))
            .collect();
        let ascii = starts
            .iter()
            .enumerate()
            .map(|(index, &start)| {
                let end = starts.get(index + 1).copied().unwrap_or(source.len());
                source[start..end].is_ascii()
            })
            .collect();

        Self { starts, ascii }
    }

    fn line_col(&self, input: &str, offset: usize) -> (usize, usize) {
        let line = self.starts.partition_point(|&start| start <= offset);
        let start = self.starts[line - 1];
        let col = if self.ascii[line - 1] {
            offset - start
        } else {
            input[start..offset].chars().count()
        };

        (line, col + 1)
    }
}

impl Span {
    fn next<'a>(self, pairs: &mut Pairs<'a, Rule>) -> Result<P<'a>> {
        pairs.next().trace_ctx("expected grammar child").at(self)
    }
}

pub fn parse(source: &str) -> Result<Program> {
    crate::with_stack(|| parse_inner(source))
}

fn parse_inner(source: &str) -> Result<Program> {
    guard_complexity(source)?;

    let mut pairs = ZakParser::parse(Rule::program, source).map_err(|error| {
        let (location, offset) = match error.location {
            pest::error::InputLocation::Pos(offset) => (Span::at_offset(source, offset), offset),
            pest::error::InputLocation::Span((start, end)) => (
                Span::at_offset(source, start).through(Span::at_offset(source, end)),
                start,
            ),
        };
        // One line for the repair prompt: pest's Display adds a multi-line
        // source excerpt, while the span already carries the location.
        let found = if source[offset..].trim().is_empty() {
            "Unexpected end of source"
        } else {
            "Unexpected input"
        };
        CompilerError::new(
            ErrorCode::SyntaxError,
            Some(location),
            format!("{found}; {}.", error.variant.message()),
        )
    })?;

    let program = Span::point(1, 1).next(&mut pairs)?;
    let seq = Span::point(1, 1).next(&mut program.into_inner())?;

    Ok(Program {
        statements: Builder {
            next_id: 0,
            lines: LineIndex::new(source),
        }
        .block(seq)?,
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
    let mut chains = ChainDepth::default();

    for (offset, ch) in source.char_indices() {
        if in_string {
            if escaped {
                escaped = false;
            } else if ch == '\\' {
                escaped = true;
            } else if ch == '"' {
                in_string = false;
                chains.previous = '"';
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

            if !ch.is_whitespace() {
                chains.significant(ch);
            }

            let message = if nesting > 32 || unary_run > 128 {
                "Prototype source/nesting budget exceeded"
            } else if chains.depth > CHAIN_BUDGET {
                "Conditional chain depth exceeds 128"
            } else {
                continue;
            };

            return Err(CompilerError::new(
                ErrorCode::ComplexityLimit,
                Some(Span::at_offset(source, offset)),
                message,
            ));
        }
    }

    Ok(())
}

const CHAIN_BUDGET: usize = 128;

/// Bounds how deeply `?` markers chain before pest builds recursive frames.
///
/// Elif chains (`?a{}:?b{}`) and nested or chained ternaries (`a?b:c?d:e`)
/// recurse once per `?` without adding delimiters, so delimiter nesting alone
/// does not bound pest's stack. Each open delimiter keeps the depth of the
/// chain inside it, and `depth` sums them along the current nesting.
///
/// A chain ends when its delimiter closes, at `;` or `,`, or after a block's
/// `}` that is not followed by `:` (elif/else). Independent conditionals
/// therefore do not add up, however many a program contains. The count must
/// never be lower than pest's recursion, so a `{` counts as a block only where
/// a map literal cannot appear: after an operand (name, literal, `)`, `]`,
/// `}`, type) or as an else block after `}:`. A map literal's `}` never ends a
/// ternary chain.
#[derive(Default)]
struct ChainDepth {
    /// Chain depth per open delimiter; index 0 is the top level.
    levels: Vec<ChainLevel>,
    depth: usize,
    previous: char,
    /// The previous significant character is a `:` right after a block.
    else_colon: bool,
}

#[derive(Default)]
struct ChainLevel {
    chain: usize,
    /// This level was opened by a block's `{`.
    block: bool,
    /// A block nested directly in this level has just closed.
    after_block: bool,
}

impl ChainDepth {
    fn top(&mut self) -> &mut ChainLevel {
        if self.levels.is_empty() {
            self.levels.push(ChainLevel::default());
        }
        self.levels.last_mut().unwrap_or_else(|| unreachable!())
    }

    fn end_chain(&mut self) {
        let ended = std::mem::take(&mut self.top().chain);
        self.depth -= ended;
    }

    fn significant(&mut self, ch: char) {
        let mut else_colon = false;

        if std::mem::take(&mut self.top().after_block) {
            if ch == ':' {
                else_colon = true;
            } else {
                // The if statement (and any elif chain) at this level is over.
                self.end_chain();
            }
        }

        match ch {
            '{' => {
                let previous = self.previous;
                let block = self.else_colon
                    || previous.is_ascii_alphanumeric()
                    || matches!(previous, '_' | '"' | ')' | ']' | '}');
                self.top();
                self.levels.push(ChainLevel {
                    block,
                    ..ChainLevel::default()
                });
            }
            '(' | '[' => {
                self.top();
                self.levels.push(ChainLevel::default());
            }
            ')' | ']' | '}' if self.levels.len() > 1 => {
                let closed = self.levels.pop().unwrap_or_default();
                self.depth -= closed.chain;
                if ch == '}' && closed.block {
                    self.top().after_block = true;
                }
            }
            ';' | ',' => self.end_chain(),
            '?' => {
                self.top().chain += 1;
                self.depth += 1;
            }
            _ => (),
        }

        self.else_colon = else_colon;
        self.previous = ch;
    }
}

struct Builder {
    next_id: u32,
    lines: LineIndex,
}

impl Builder {
    fn span(&self, pair: &P<'_>) -> Span {
        let range = pair.as_span();
        let input = range.get_input();
        let (line, col) = self.lines.line_col(input, range.start());
        let (end_line, end_col) = self.lines.line_col(input, range.end());

        Span {
            start: range.start(),
            end: range.end(),
            line,
            col,
            end_line,
            end_col,
        }
    }

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
            span: self.span(&pair),
        }
    }

    fn block(&mut self, pair: P<'_>) -> Result<Vec<Stmt>> {
        if pair.as_rule() == Rule::block {
            return self.block(Span::point(1, 1).next(&mut pair.into_inner())?);
        }
        pair.into_inner().map(|pair| self.statement(pair)).collect()
    }

    fn ty(&self, pair: P<'_>) -> Result<Type> {
        let location = self.span(&pair);
        let kind = pair.as_rule();
        let text = pair.as_str();
        let mut children = pair.clone().into_inner();

        Ok(match kind {
            Rule::ty => self.ty(location.next(&mut children)?)?,
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
            Rule::array_type => Type::array(self.ty(location.next(&mut children)?)?),
            Rule::map_type => Type::map(
                self.ty(location.next(&mut children)?)?,
                self.ty(location.next(&mut children)?)?,
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
        let location = self.span(&pair);
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
                let name = location.next(&mut children)?.as_str().to_owned();
                let value_or_type = location.next(&mut children)?;
                let (declared_type, value) = if value_or_type.as_rule() == Rule::ty {
                    (
                        Some(self.ty(value_or_type)?),
                        self.expression(location.next(&mut children)?)?,
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
                let target = self.expression(location.next(&mut children)?)?;
                let op = location.next(&mut children)?;
                let operator = if op.as_str() == "=" {
                    AssignOp::Set
                } else {
                    AssignOp::Augmented(Self::binary(&op.as_str()[..1], location)?)
                };
                StmtKind::Assign {
                    target,
                    operator,
                    value: self.expression(location.next(&mut children)?)?,
                }
            }
            Rule::append => StmtKind::Append {
                target: self.expression(location.next(&mut children)?)?,
                value: self.expression(location.next(&mut children)?)?,
            },
            Rule::return_stmt => StmtKind::Return(self.expression(location.next(&mut children)?)?),
            Rule::break_stmt => StmtKind::Break,
            Rule::continue_stmt => StmtKind::Continue,
            Rule::if_stmt => {
                let condition = self.expression(location.next(&mut children)?)?;
                let then_body = self.block(location.next(&mut children)?)?;
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
                condition: self.expression(location.next(&mut children)?)?,
                body: self.block(location.next(&mut children)?)?,
            },
            Rule::for_stmt => {
                let names = location
                    .next(&mut children)?
                    .into_inner()
                    .map(|p| self.binding(p))
                    .collect();
                let iteration = self.iteration(location.next(&mut children)?)?;
                StmtKind::For {
                    names,
                    iteration,
                    body: self.block(location.next(&mut children)?)?,
                }
            }
            Rule::function => {
                let name = location.next(&mut children)?.as_str().to_owned();
                let parameters_or_type = location.next(&mut children)?;
                let mut parameters = vec![];
                let return_type = if parameters_or_type.as_rule() == Rule::params {
                    for param in parameters_or_type.into_inner() {
                        let mut fields = param.into_inner();
                        let binding = self.binding(location.next(&mut fields)?);
                        parameters.push(Parameter {
                            binding,
                            ty: self.ty(location.next(&mut fields)?)?,
                        });
                    }
                    self.ty(location.next(&mut children)?)?
                } else {
                    self.ty(parameters_or_type)?
                };

                StmtKind::Function(Function {
                    name,
                    parameters,
                    return_type,
                    body: self.block(location.next(&mut children)?)?,
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
        let location = self.span(&pair);
        let mut children = pair.into_inner();
        let start = self.expression(location.next(&mut children)?)?;
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
        let location = self.span(&pair);
        let rule = pair.as_rule();
        let text = pair.as_str();
        let mut children = pair.clone().into_inner();
        let kind = match rule {
            Rule::expr | Rule::parenthesized | Rule::lower | Rule::upper => {
                return self.expression(location.next(&mut children)?);
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
                        let name = location.next(&mut fields)?.as_str().to_owned();
                        let iteration = Box::new(self.iteration(location.next(&mut fields)?)?);
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
                        self.expression(location.next(&mut fields)?)?,
                        self.expression(location.next(&mut fields)?)?,
                    ));
                }
                ExprKind::Map(entries)
            }
            Rule::cast => ExprKind::Cast(
                self.ty(location.next(&mut children)?)?,
                Box::new(self.expression(location.next(&mut children)?)?),
            ),
            Rule::call => {
                let name = location.next(&mut children)?.as_str().to_owned();
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
                let condition = self.expression(location.next(&mut children)?)?;
                let Some(then_value) = children.next() else {
                    return Ok(condition);
                };
                ExprKind::Conditional {
                    condition: Box::new(condition),
                    then_value: Box::new(self.expression(then_value)?),
                    else_value: Box::new(self.expression(location.next(&mut children)?)?),
                }
            }
            Rule::or_expr | Rule::and_expr | Rule::compare | Rule::sum | Rule::product => {
                let mut value = self.expression(location.next(&mut children)?)?;

                while let Some(op) = children.next() {
                    let right = self.expression(location.next(&mut children)?)?;
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
                        self.span(&prefix).through(value.span),
                        ExprKind::Unary(op, Box::new(value)),
                    )?;
                }
                return Ok(value);
            }
            Rule::post | Rule::target => {
                let mut value = self.expression(location.next(&mut children)?)?;
                for suffix in children {
                    let span = value.span.through(self.span(&suffix));
                    let suffix_rule = suffix.as_rule();
                    let mut fields = suffix.into_inner();
                    let kind = if suffix_rule == Rule::index_suffix {
                        ExprKind::Index(
                            Box::new(value),
                            Box::new(self.expression(span.next(&mut fields)?)?),
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

#[cfg(test)]
mod tests {
    use super::LineIndex;

    #[test]
    fn line_index_matches_pest_coordinates_at_every_char_boundary() {
        for input in [
            "",
            "x:=1",
            "x:=1;\nout(x)\n",
            "a:=\"é✓\";\r\nout(a)\r\n\r\nb:=2",
            "lone\rcarriage\n\nend",
            "s:=\"日本\";\nt:=\"ok\"",
        ] {
            let lines = LineIndex::new(input);
            for offset in (0..=input.len()).filter(|&offset| input.is_char_boundary(offset)) {
                let expected = pest::Position::new(input, offset).unwrap().line_col();
                assert_eq!(
                    lines.line_col(input, offset),
                    expected,
                    "{input:?} at {offset}"
                );
            }
        }
    }
}
