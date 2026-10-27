//! Strict Zak inference and name resolution. Rust inference does not replace these rules.
use crate::{
    ast::*,
    error::{CompilerError, ErrorCode},
};
use std::collections::{HashMap, HashSet};

type Result<T> = std::result::Result<T, CompilerError>;

#[derive(Clone, Copy, Debug, PartialEq, Eq, strum::EnumString, strum::Display, strum::EnumIter)]
#[strum(serialize_all = "lowercase")]
pub enum Builtin {
    Out,
    Abs,
    Min,
    Max,
    Sum,
    Srt,
    Rev,
    Keys,
    Vals,
    Pop,
    Del,
    Spl,
    Jn,
    Up,
    Lo,
}

#[derive(Clone, Debug)]
pub(crate) struct Symbol {
    pub python: String,
    pub module: bool,
}

#[derive(Clone, Debug)]
pub(crate) struct Signature {
    pub symbol: Symbol,
    pub parameters: Vec<Type>,
    pub return_type: Type,
}

#[derive(Clone, Debug)]
struct Binding {
    symbol: Symbol,
    ty: Type,
}

/// Only `check` can construct this value; emission cannot accept unchecked syntax.
#[derive(Debug)]
#[cfg_attr(feature = "python", pyo3::pyclass(module = "zakc"))]
pub struct CheckedProgram {
    pub(crate) program: Program,
    pub(crate) types: HashMap<NodeId, Type>,
    pub(crate) symbols: HashMap<NodeId, Symbol>,
    pub(crate) functions: HashMap<String, Signature>,
}

impl CheckedProgram {
    pub fn syntax(&self) -> &Program {
        &self.program
    }

    pub fn expression_types(&self) -> &HashMap<NodeId, Type> {
        &self.types
    }
}

struct Checker {
    errors: Vec<CompilerError>,
    types: HashMap<NodeId, Type>,
    symbols: HashMap<NodeId, Symbol>,
    scopes: Vec<HashMap<String, Binding>>,
    functions: HashMap<String, Signature>,
    next_variable: usize,
    return_type: Option<Type>,
    loop_depth: usize,
}

impl Program {
    pub fn check(self) -> std::result::Result<CheckedProgram, Vec<CompilerError>> {
        crate::with_stack(|| self.check_inner())
    }

    /// Validate the public syntax boundary before any ID-indexed metadata is built.
    /// A cloned/combined tree may contain identities from multiple independent parses.
    fn validate_tree(&self) -> Result<()> {
        enum Visit<'a> {
            Statement(&'a Stmt),
            Expression(&'a Expr),
            Binding(&'a BindingName),
        }

        let mut work: Vec<_> = self
            .statements
            .iter()
            .rev()
            .map(|s| (Visit::Statement(s), 0usize))
            .collect();

        let mut seen = HashSet::new();

        while let Some((item, depth)) = work.pop() {
            let (id, span) = match &item {
                Visit::Statement(node) => (node.id, node.span),
                Visit::Expression(node) => (node.id, node.span),
                Visit::Binding(node) => (node.id, node.span),
            };

            if depth > 128 {
                return Err(span.error(
                    ErrorCode::ComplexityLimit,
                    "Syntax tree exceeds the prototype depth budget",
                ));
            }

            if !seen.insert(id) {
                return Err(
                    span.error(
                    ErrorCode::InvalidAst,
                    "Duplicate syntax node ID; independent parsed trees cannot be combined without reassigning identities",
                ));
            }

            let depth = depth + 1;

            match item {
                Visit::Binding(_) => (),
                Visit::Statement(node) => match &node.kind {
                    StmtKind::Declare { value, .. }
                    | StmtKind::Return(value)
                    | StmtKind::Call(value) => work.push((Visit::Expression(value), depth)),
                    StmtKind::Assign { target, value, .. } | StmtKind::Append { target, value } => {
                        work.push((Visit::Expression(value), depth));
                        work.push((Visit::Expression(target), depth));
                    }
                    StmtKind::If {
                        condition,
                        then_body,
                        else_body,
                    } => {
                        work.extend(else_body.iter().rev().map(|s| (Visit::Statement(s), depth)));
                        work.extend(then_body.iter().rev().map(|s| (Visit::Statement(s), depth)));
                        work.push((Visit::Expression(condition), depth));
                    }
                    StmtKind::While { condition, body } => {
                        work.extend(body.iter().rev().map(|s| (Visit::Statement(s), depth)));
                        work.push((Visit::Expression(condition), depth));
                    }
                    StmtKind::For {
                        names,
                        iteration,
                        body,
                    } => {
                        work.extend(body.iter().rev().map(|s| (Visit::Statement(s), depth)));
                        work.extend(names.iter().rev().map(|n| (Visit::Binding(n), depth)));

                        if let Some(stop) = &iteration.stop {
                            work.push((Visit::Expression(stop), depth));
                        }

                        work.push((Visit::Expression(&iteration.start), depth));
                    }
                    StmtKind::Function(function) => {
                        work.extend(
                            function
                                .body
                                .iter()
                                .rev()
                                .map(|s| (Visit::Statement(s), depth)),
                        );
                        work.extend(
                            function
                                .parameters
                                .iter()
                                .rev()
                                .map(|p| (Visit::Binding(&p.binding), depth)),
                        );
                    }
                    StmtKind::Break | StmtKind::Continue => (),
                },
                Visit::Expression(node) => match &node.kind {
                    ExprKind::Literal(_) | ExprKind::Name(_) => (),
                    ExprKind::Array(items) => {
                        work.extend(items.iter().rev().map(|e| (Visit::Expression(e), depth)))
                    }
                    ExprKind::Map(items) => {
                        for (k, v) in items.iter().rev() {
                            work.push((Visit::Expression(v), depth));
                            work.push((Visit::Expression(k), depth));
                        }
                    }
                    ExprKind::Unary(_, value) | ExprKind::Cast(_, value) => {
                        work.push((Visit::Expression(value), depth))
                    }
                    ExprKind::Binary(left, _, right) | ExprKind::Index(left, right) => {
                        work.push((Visit::Expression(right), depth));
                        work.push((Visit::Expression(left), depth));
                    }
                    ExprKind::Conditional {
                        condition,
                        then_value,
                        else_value,
                    } => {
                        work.push((Visit::Expression(else_value), depth));
                        work.push((Visit::Expression(then_value), depth));
                        work.push((Visit::Expression(condition), depth));
                    }
                    ExprKind::Call { arguments, .. } => work.extend(
                        arguments
                            .iter()
                            .rev()
                            .map(|e| (Visit::Expression(e), depth)),
                    ),
                    ExprKind::Slice {
                        collection,
                        lower,
                        upper,
                    } => {
                        for bound in [lower, upper].into_iter().flatten() {
                            work.push((Visit::Expression(bound), depth));
                        }

                        work.push((Visit::Expression(collection), depth));
                    }
                    ExprKind::Comprehension {
                        value,
                        iteration,
                        condition,
                        ..
                    } => {
                        if let Some(condition) = condition {
                            work.push((Visit::Expression(condition), depth));
                        }

                        if let Some(stop) = &iteration.stop {
                            work.push((Visit::Expression(stop), depth));
                        }

                        work.push((Visit::Expression(&iteration.start), depth));
                        work.push((Visit::Expression(value), depth));
                    }
                },
            }
        }
        Ok(())
    }

    fn check_inner(self) -> std::result::Result<CheckedProgram, Vec<CompilerError>> {
        self.validate_tree().map_err(|error| vec![error])?;

        let mut checker = Checker {
            errors: vec![],
            types: HashMap::new(),
            symbols: HashMap::new(),
            scopes: vec![HashMap::new()],
            functions: HashMap::new(),
            next_variable: 0,
            return_type: None,
            loop_depth: 0,
        };

        for statement in &self.statements {
            if let StmtKind::Function(function) = &statement.kind {
                let name = &function.name;

                if name.parse::<Builtin>().is_ok() {
                    checker.errors.push(
                        statement
                            .span
                            .error(ErrorCode::ReservedName, format!("'{name}' is a builtin")),
                    );
                } else if checker.functions.contains_key(name) {
                    checker.errors.push(statement.span.error(
                        ErrorCode::DuplicateName,
                        format!("Function '{name}' is already defined"),
                    ));
                } else {
                    let symbol = Symbol {
                        python: format!("_ZAK_f{}", checker.functions.len()),
                        module: true,
                    };

                    checker.symbols.insert(statement.id, symbol.clone());
                    checker.functions.insert(
                        name.clone(),
                        Signature {
                            symbol,
                            parameters: function.parameters.iter().map(|p| p.ty.clone()).collect(),
                            return_type: function.return_type.clone(),
                        },
                    );
                }
            }
        }

        checker.block(&self.statements, false);

        if !checker.errors.is_empty() {
            return Err(checker.errors);
        }

        Ok(CheckedProgram {
            program: self,
            types: checker.types,
            symbols: checker.symbols,
            functions: checker.functions,
        })
    }
}

impl Span {
    #[track_caller]
    fn error(self, code: ErrorCode, message: impl Into<String>) -> CompilerError {
        CompilerError::new(code, Some(self), message)
    }
}

impl Type {
    pub fn validate(&self, span: Span) -> Result<()> {
        Checker::validate_type(span, self)
    }
}

impl Checker {
    #[track_caller]
    fn expect(&self, span: Span, actual: &Type, expected: &Type) -> Result<()> {
        if actual != expected {
            Err(span.error(
                ErrorCode::TypeMismatch,
                format!("Expected {expected}, got {actual}"),
            ))
        } else {
            Ok(())
        }
    }

    fn validate_type(span: Span, ty: &Type) -> Result<()> {
        match ty {
            Type::Array(t) => Self::validate_type(span, t),
            Type::Map(k, v) => {
                if !matches!(**k, Type::Int | Type::Str) {
                    return Err(
                        span.error(ErrorCode::InvalidType, "Map keys must have type I or S")
                    );
                }

                Self::validate_type(span, v)
            }
            _ => Ok(()),
        }
    }
    fn bind(&mut self, id: NodeId, span: Span, name: &str, ty: Type) -> Result<()> {
        if name.parse::<Builtin>().is_ok() || self.functions.contains_key(name) {
            return Err(span.error(
                ErrorCode::ReservedName,
                format!("'{name}' is a function name"),
            ));
        }

        let module = self.scopes.len() == 1;
        let scope = self.scopes.last_mut().expect("checker always owns a scope");

        if scope.contains_key(name) {
            return Err(span.error(
                ErrorCode::DuplicateName,
                format!("'{name}' is already declared"),
            ));
        }

        let symbol = Symbol {
            python: format!("_ZAK_v{}", self.next_variable),
            module,
        };

        self.next_variable += 1;
        self.symbols.insert(id, symbol.clone());
        scope.insert(name.to_owned(), Binding { symbol, ty });

        Ok(())
    }

    fn lookup(&mut self, node: &Expr, name: &str) -> Result<Type> {
        let binding = self
            .scopes
            .iter()
            .rev()
            .find_map(|scope| scope.get(name))
            .cloned()
            .ok_or_else(|| {
                node.span
                    .error(ErrorCode::UndefinedName, format!("Undefined name '{name}'"))
            })?;

        self.symbols.insert(node.id, binding.symbol);

        Ok(binding.ty)
    }

    fn block(&mut self, statements: &[Stmt], child: bool) {
        if child {
            self.scopes.push(HashMap::new());
        }

        for statement in statements {
            if let Err(error) = self.statement(statement) {
                self.errors.push(error);
            }
        }

        if child {
            self.scopes.pop();
        }
    }

    fn statement(&mut self, node: &Stmt) -> Result<()> {
        match &node.kind {
            StmtKind::Declare {
                name,
                declared_type,
                value,
            } => {
                if let Some(ty) = declared_type {
                    Self::validate_type(node.span, ty)?;
                }

                let ty = self.value(value, declared_type.as_ref())?;
                self.bind(node.id, node.span, name, ty)?;
            }
            StmtKind::Assign {
                target,
                operator,
                value,
            } => {
                let ty = self.target(target)?;
                let actual = self.value(value, Some(&ty))?;

                if let AssignOp::Augmented(op) = operator {
                    self.binary(node.span, &ty, *op, &actual)?;
                }
            }
            StmtKind::Append { target, value } => {
                let Type::Array(element) = self.target(target)? else {
                    return Err(target
                        .span
                        .error(ErrorCode::TypeMismatch, "Append requires an array"));
                };

                self.value(value, Some(&element))?;
            }
            StmtKind::Return(value) => {
                let ty = self.return_type.clone().ok_or_else(|| {
                    node.span
                        .error(ErrorCode::InvalidControlFlow, "Return requires a function")
                })?;

                self.value(value, Some(&ty))?;
            }
            StmtKind::Break | StmtKind::Continue => {
                if self.loop_depth == 0 {
                    return Err(node.span.error(
                        ErrorCode::InvalidControlFlow,
                        "Break/continue requires a loop",
                    ));
                }
            }
            StmtKind::Call(call) => {
                self.call(call)?;
            }
            StmtKind::If {
                condition,
                then_body,
                else_body,
            } => {
                self.value(condition, Some(&Type::Bool))?;
                self.block(then_body, true);
                self.block(else_body, true);
            }
            StmtKind::While { condition, body } => {
                self.value(condition, Some(&Type::Bool))?;
                self.loop_depth += 1;
                self.block(body, true);
                self.loop_depth -= 1;
            }
            StmtKind::For {
                names,
                iteration,
                body,
            } => {
                let types = self.iteration(iteration, names.len())?;

                self.scopes.push(HashMap::new());
                self.loop_depth += 1;

                let result: Result<()> = (|| {
                    for (name, ty) in names.iter().zip(types) {
                        self.bind(name.id, name.span, &name.name, ty)?;
                    }
                    self.block(body, false);
                    Ok(())
                })();

                self.loop_depth -= 1;
                self.scopes.pop();

                result?;
            }
            StmtKind::Function(function) => self.function(node, function)?,
        }
        Ok(())
    }

    fn function(&mut self, node: &Stmt, function: &Function) -> Result<()> {
        if self.scopes.len() != 1 || self.return_type.is_some() {
            return Err(node.span.error(
                ErrorCode::UnsupportedFeature,
                "Functions must be declared at top level",
            ));
        }

        function.return_type.validate(node.span)?;

        let saved_return = self.return_type.replace(function.return_type.clone());
        let saved_loop = std::mem::replace(&mut self.loop_depth, 0);

        self.scopes.push(HashMap::new());

        let result = (|| {
            for param in &function.parameters {
                param.ty.validate(param.binding.span)?;

                self.bind(
                    param.binding.id,
                    param.binding.span,
                    &param.binding.name,
                    param.ty.clone(),
                )?;
            }

            self.block(&function.body, false);

            if !returns(&function.body) {
                return Err(node.span.error(
                    ErrorCode::MissingReturn,
                    format!("Function '{}' must return on every path", function.name),
                ));
            }

            Ok(())
        })();

        self.scopes.pop();
        self.return_type = saved_return;
        self.loop_depth = saved_loop;

        result
    }

    fn iteration(&mut self, node: &Iteration, count: usize) -> Result<Vec<Type>> {
        let types = if let Some(stop) = &node.stop {
            self.value(&node.start, Some(&Type::Int))?;
            self.value(stop, Some(&Type::Int))?;
            vec![Type::Int]
        } else {
            match self.value(&node.start, None)? {
                Type::Array(t) => vec![*t],
                Type::Str => vec![Type::Str],
                Type::Map(k, v) => {
                    if count == 2 {
                        vec![*k, *v]
                    } else {
                        vec![*k]
                    }
                }
                _ => {
                    return Err(node.span.error(
                        ErrorCode::InvalidIteration,
                        "Expected an array, string, map, or integer range",
                    ));
                }
            }
        };

        if count != types.len() {
            return Err(node.span.error(
                ErrorCode::InvalidIteration,
                "Two loop variables require a map",
            ));
        }
        Ok(types)
    }

    fn target(&mut self, node: &Expr) -> Result<Type> {
        let ty = match &node.kind {
            ExprKind::Name(name) => self.lookup(node, name)?,
            ExprKind::Index(collection, index) => {
                let ty = self.target(collection)?;

                if ty == Type::Str {
                    return Err(node
                        .span
                        .error(ErrorCode::InvalidTarget, "Strings cannot be mutated"));
                }

                self.index(node.span, &ty, index)?
            }
            _ => {
                return Err(node.span.error(
                    ErrorCode::InvalidTarget,
                    "Target must be rooted in a variable",
                ));
            }
        };

        self.types.insert(node.id, ty.clone());

        Ok(ty)
    }

    fn index(&mut self, span: Span, ty: &Type, index: &Expr) -> Result<Type> {
        match ty {
            Type::Map(k, v) => {
                self.value(index, Some(k))?;
                Ok(*v.clone())
            }
            Type::Array(t) => {
                self.value(index, Some(&Type::Int))?;
                Ok(*t.clone())
            }
            Type::Str => {
                self.value(index, Some(&Type::Int))?;
                Ok(Type::Str)
            }
            _ => Err(span.error(
                ErrorCode::TypeMismatch,
                "Indexing requires array, map or string",
            )),
        }
    }
    fn value(&mut self, node: &Expr, expected: Option<&Type>) -> Result<Type> {
        let ty = self.expression(node, expected)?;

        if ty == Type::Void {
            return Err(node
                .span
                .error(ErrorCode::VoidValue, "This call does not return a value"));
        }

        if let Some(expected) = expected {
            self.expect(node.span, &ty, expected)?;
        }

        self.types.insert(node.id, ty.clone());

        Ok(ty)
    }
    fn expression(&mut self, node: &Expr, expected: Option<&Type>) -> Result<Type> {
        Ok(match &node.kind {
            ExprKind::Literal(literal) => match literal {
                Literal::Int(_) => Type::Int,
                Literal::Real(_) => Type::Real,
                Literal::Bool(_) => Type::Bool,
                Literal::Str(_) => Type::Str,
            },
            ExprKind::Name(name) => self.lookup(node, name)?,
            ExprKind::Array(items) => {
                let mut element = match expected {
                    Some(Type::Array(t)) => Some(*t.clone()),
                    _ => None,
                };

                for item in items {
                    let ty = self.value(item, element.as_ref())?;
                    element.get_or_insert(ty);
                }

                Type::array(element.ok_or_else(|| {
                    node.span.error(
                        ErrorCode::CannotInferType,
                        "An empty array needs contextual type",
                    )
                })?)
            }
            ExprKind::Map(entries) => {
                let (mut key, mut value) = match expected {
                    Some(Type::Map(k, v)) => (Some(*k.clone()), Some(*v.clone())),
                    _ => (None, None),
                };

                for (k, v) in entries {
                    let kt = self.value(k, key.as_ref())?;
                    let vt = self.value(v, value.as_ref())?;

                    if !matches!(kt, Type::Int | Type::Str) {
                        return Err(k
                            .span
                            .error(ErrorCode::InvalidType, "Map keys must have type I or S"));
                    }

                    key.get_or_insert(kt);
                    value.get_or_insert(vt);
                }
                Type::map(
                    key.ok_or_else(|| {
                        node.span.error(
                            ErrorCode::CannotInferType,
                            "An empty map needs contextual type",
                        )
                    })?,
                    value.ok_or_else(|| {
                        node.span.error(
                            ErrorCode::CannotInferType,
                            "An empty map needs contextual type",
                        )
                    })?,
                )
            }
            ExprKind::Unary(op, operand) => {
                let ty = self.value(operand, None)?;

                match op {
                    UnaryOp::Not => {
                        self.expect(node.span, &ty, &Type::Bool)?;
                        Type::Bool
                    }
                    UnaryOp::Len if matches!(ty, Type::Array(_) | Type::Map(_, _) | Type::Str) => {
                        Type::Int
                    }
                    UnaryOp::Neg if ty.numeric() => ty,
                    _ => {
                        return Err(node.span.error(
                            ErrorCode::TypeMismatch,
                            "Invalid operand for unary operator",
                        ));
                    }
                }
            }
            ExprKind::Binary(left, op, right) => {
                let context = if *op == BinaryOp::Add { expected } else { None };
                let (l, r) = if *op == BinaryOp::In {
                    (self.value(left, None)?, self.value(right, None)?)
                } else {
                    match self.value(left, context) {
                        Ok(l) => {
                            let r = self.value(right, Some(&l))?;
                            (l, r)
                        }
                        Err(e) if e.code == ErrorCode::CannotInferType => {
                            let r = self.value(right, context)?;
                            let l = self.value(left, Some(&r))?;
                            (l, r)
                        }
                        Err(e) => return Err(e),
                    }
                };

                self.binary(node.span, &l, *op, &r)?
            }
            ExprKind::Conditional {
                condition,
                then_value,
                else_value,
            } => {
                self.value(condition, Some(&Type::Bool))?;
                let ty = self.value(then_value, expected)?;
                self.value(else_value, Some(&ty))?;
                ty
            }
            ExprKind::Index(collection, index) => {
                let ty = self.value(collection, None)?;
                self.index(node.span, &ty, index)?
            }
            ExprKind::Slice {
                collection,
                lower,
                upper,
            } => {
                let ty = self.value(collection, None)?;

                if !matches!(ty, Type::Str | Type::Array(_)) {
                    return Err(node
                        .span
                        .error(ErrorCode::TypeMismatch, "Slicing requires array or string"));
                }

                for bound in [lower, upper].into_iter().flatten() {
                    self.value(bound, Some(&Type::Int))?;
                }

                ty
            }
            ExprKind::Cast(ty, value) => {
                if !self.value(value, None)?.primitive() {
                    return Err(node
                        .span
                        .error(ErrorCode::TypeMismatch, "Casts require primitive values"));
                }
                ty.clone()
            }
            ExprKind::Call { .. } => self.call(node)?,
            ExprKind::Comprehension { .. } => {
                return Err(node.span.error(
                    ErrorCode::UnsupportedFeature,
                    "Comprehensions are outside SD1",
                ));
            }
        })
    }
    fn binary(&self, span: Span, left: &Type, op: BinaryOp, right: &Type) -> Result<Type> {
        if op == BinaryOp::In {
            match right {
                Type::Map(k, _) | Type::Array(k) => self.expect(span, left, k)?,
                Type::Str => self.expect(span, left, &Type::Str)?,
                _ => {
                    return Err(span.error(
                        ErrorCode::TypeMismatch,
                        "Membership requires array, map or string",
                    ));
                }
            }
            return Ok(Type::Bool);
        }

        self.expect(span, right, left)?;

        match op {
            BinaryOp::And | BinaryOp::Or => {
                self.expect(span, left, &Type::Bool)?;
                Ok(Type::Bool)
            }
            BinaryOp::Eq | BinaryOp::Ne => Ok(Type::Bool),
            BinaryOp::Lt | BinaryOp::Le | BinaryOp::Gt | BinaryOp::Ge
                if left.numeric() || *left == Type::Str =>
            {
                Ok(Type::Bool)
            }
            BinaryOp::Add if matches!(left, Type::Str | Type::Array(_)) => Ok(left.clone()),
            BinaryOp::Add | BinaryOp::Sub | BinaryOp::Mul | BinaryOp::Div | BinaryOp::Mod
                if left.numeric() =>
            {
                Ok(left.clone())
            }
            _ => Err(span.error(ErrorCode::TypeMismatch, "Invalid operands for operator")),
        }
    }

    fn call(&mut self, node: &Expr) -> Result<Type> {
        let ExprKind::Call { name, arguments } = &node.kind else {
            return Err(node.span.error(ErrorCode::InternalError, "Expected call"));
        };
        let ty = if let Some(signature) = self.functions.get(name).cloned() {
            self.arity(node, arguments.len(), signature.parameters.len())?;

            for (argument, ty) in arguments.iter().zip(&signature.parameters) {
                self.value(argument, Some(ty))?;
            }

            self.symbols.insert(node.id, signature.symbol);
            signature.return_type
        } else {
            let builtin = name.parse::<Builtin>().map_err(|_| {
                node.span.error(
                    ErrorCode::UndefinedName,
                    format!("Undefined function '{name}'"),
                )
            })?;
            let arity = if matches!(
                builtin,
                Builtin::Min | Builtin::Max | Builtin::Spl | Builtin::Jn | Builtin::Del
            ) {
                2
            } else {
                1
            };

            self.arity(node, arguments.len(), arity)?;
            self.builtin(node, builtin, arguments)?
        };

        self.types.insert(node.id, ty.clone());
        Ok(ty)
    }

    fn arity(&self, node: &Expr, actual: usize, expected: usize) -> Result<()> {
        if actual != expected {
            Err(node.span.error(
                ErrorCode::CallArity,
                format!("Expected {expected} arguments, got {actual}"),
            ))
        } else {
            Ok(())
        }
    }

    fn builtin(&mut self, node: &Expr, builtin: Builtin, arguments: &[Expr]) -> Result<Type> {
        if builtin == Builtin::Jn {
            self.value(&arguments[0], Some(&Type::array(Type::Str)))?;
            self.value(&arguments[1], Some(&Type::Str))?;
            return Ok(Type::Str);
        }

        let first = self.value(&arguments[0], None)?;

        Ok(match builtin {
            Builtin::Out => Type::Void,
            Builtin::Abs | Builtin::Min | Builtin::Max => {
                if !first.numeric() {
                    return Err(node
                        .span
                        .error(ErrorCode::TypeMismatch, "Expected numeric values"));
                }

                if arguments.len() == 2 {
                    self.value(&arguments[1], Some(&first))?;
                }

                first
            }
            Builtin::Up | Builtin::Lo | Builtin::Spl => {
                self.expect(arguments[0].span, &first, &Type::Str)?;

                if builtin == Builtin::Spl {
                    self.value(&arguments[1], Some(&Type::Str))?;
                    Type::array(Type::Str)
                } else {
                    Type::Str
                }
            }
            Builtin::Keys | Builtin::Vals | Builtin::Del => {
                let Type::Map(k, v) = first else {
                    return Err(node.span.error(ErrorCode::TypeMismatch, "Expected a map"));
                };

                if builtin == Builtin::Del {
                    self.value(&arguments[1], Some(&k))?;
                    Type::Void
                } else {
                    Type::array(if builtin == Builtin::Keys { *k } else { *v })
                }
            }
            Builtin::Sum | Builtin::Srt | Builtin::Rev | Builtin::Pop => {
                let Type::Array(t) = &first else {
                    return Err(node
                        .span
                        .error(ErrorCode::TypeMismatch, "Expected an array"));
                };

                if builtin == Builtin::Sum && !t.numeric() {
                    return Err(node
                        .span
                        .error(ErrorCode::TypeMismatch, "Sum requires numeric elements"));
                }

                if builtin == Builtin::Srt && !matches!(**t, Type::Int | Type::Real | Type::Str) {
                    return Err(node.span.error(
                        ErrorCode::TypeMismatch,
                        "Sort requires numeric or string elements",
                    ));
                }

                if matches!(builtin, Builtin::Sum | Builtin::Pop) {
                    *t.clone()
                } else {
                    first
                }
            }
            Builtin::Jn => unreachable!("join checked before unconstrained argument inference"),
        })
    }
}

fn returns(statements: &[Stmt]) -> bool {
    statements.iter().any(|statement| match &statement.kind {
        StmtKind::Return(_) => true,
        StmtKind::If {
            then_body,
            else_body,
            ..
        } => returns(then_body) && returns(else_body),
        _ => false,
    })
}
