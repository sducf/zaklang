//! Compiler-owned syntax, with stable identities and one-based source coordinates.
use serde::Serialize;

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub struct Span {
    pub start: usize,
    pub end: usize,
    pub line: usize,
    pub col: usize,
    pub end_line: usize,
    pub end_col: usize,
}

impl Span {
    pub fn at_offset(source: &str, offset: usize) -> Self {
        let mut offset = offset.min(source.len());
        while !source.is_char_boundary(offset) {
            offset -= 1;
        }
        let prefix = &source[..offset];
        let line = prefix.bytes().filter(|&ch| ch == b'\n').count() + 1;
        let col = prefix.rsplit('\n').next().unwrap_or("").chars().count() + 1;
        Self {
            start: offset,
            end: offset,
            line,
            col,
            end_line: line,
            end_col: col,
        }
    }
    pub fn point(line: usize, col: usize) -> Self {
        Self {
            start: 0,
            end: 0,
            line,
            col,
            end_line: line,
            end_col: col,
        }
    }
    pub fn through(self, end: Self) -> Self {
        Self {
            end: end.end,
            end_line: end.end_line,
            end_col: end.end_col,
            ..self
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, Serialize)]
#[serde(transparent)]
pub struct NodeId(pub u32);

#[derive(Clone, Debug, PartialEq, Eq, Serialize, derive_more::Display)]
pub enum Type {
    #[display("I")]
    Int,
    #[display("R")]
    Real,
    #[display("B")]
    Bool,
    #[display("S")]
    Str,
    #[display("[{_0}]")]
    Array(Box<Type>),
    #[display("{{{_0}:{_1}}}")]
    Map(Box<Type>, Box<Type>),
    #[display("void")]
    Void,
}

impl Type {
    pub fn array(element: Type) -> Self {
        Self::Array(Box::new(element))
    }
    pub fn map(key: Type, value: Type) -> Self {
        Self::Map(Box::new(key), Box::new(value))
    }
    pub fn numeric(&self) -> bool {
        matches!(self, Self::Int | Self::Real)
    }
    pub fn primitive(&self) -> bool {
        matches!(self, Self::Int | Self::Real | Self::Bool | Self::Str)
    }
}

#[derive(
    Clone, Copy, Debug, PartialEq, Eq, Serialize, strum::EnumString, strum::Display, strum::EnumIter,
)]
pub enum BinaryOp {
    #[strum(serialize = "+")]
    Add,
    #[strum(serialize = "-")]
    Sub,
    #[strum(serialize = "*")]
    Mul,
    #[strum(serialize = "/")]
    Div,
    #[strum(serialize = "%")]
    Mod,
    #[strum(serialize = "==")]
    Eq,
    #[strum(serialize = "!=")]
    Ne,
    #[strum(serialize = "<")]
    Lt,
    #[strum(serialize = "<=")]
    Le,
    #[strum(serialize = ">")]
    Gt,
    #[strum(serialize = ">=")]
    Ge,
    #[strum(serialize = "&")]
    And,
    #[strum(serialize = "|")]
    Or,
    #[strum(serialize = "@")]
    In,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum UnaryOp {
    Neg,
    Not,
    Len,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
pub enum AssignOp {
    Set,
    Augmented(BinaryOp),
}

#[derive(Clone, Debug, Serialize)]
pub enum Literal {
    Int(String),
    Real(String),
    Bool(bool),
    Str(String),
}
#[derive(Clone, Debug, Serialize)]
pub struct Expr {
    pub id: NodeId,
    pub span: Span,
    pub kind: ExprKind,
    #[serde(skip)]
    pub(crate) depth: usize,
}
#[derive(Clone, Debug, Serialize)]
pub enum ExprKind {
    Literal(Literal),
    Name(String),
    Array(Vec<Expr>),
    Map(Vec<(Expr, Expr)>),
    Unary(UnaryOp, Box<Expr>),
    Binary(Box<Expr>, BinaryOp, Box<Expr>),
    Conditional {
        condition: Box<Expr>,
        then_value: Box<Expr>,
        else_value: Box<Expr>,
    },
    Call {
        name: String,
        arguments: Vec<Expr>,
    },
    Cast(Type, Box<Expr>),
    Index(Box<Expr>, Box<Expr>),
    Slice {
        collection: Box<Expr>,
        lower: Option<Box<Expr>>,
        upper: Option<Box<Expr>>,
    },
    Comprehension {
        value: Box<Expr>,
        name: String,
        iteration: Box<Iteration>,
        condition: Option<Box<Expr>>,
    },
}

#[derive(Clone, Debug, Serialize)]
pub struct Iteration {
    pub span: Span,
    pub start: Expr,
    pub stop: Option<Expr>,
}
#[derive(Clone, Debug, Serialize)]
pub struct BindingName {
    pub id: NodeId,
    pub name: String,
    pub span: Span,
}
#[derive(Clone, Debug, Serialize)]
pub struct Parameter {
    pub binding: BindingName,
    pub ty: Type,
}
#[derive(Clone, Debug, Serialize)]
pub struct Function {
    pub name: String,
    pub parameters: Vec<Parameter>,
    pub return_type: Type,
    pub body: Vec<Stmt>,
}
#[derive(Clone, Debug, Serialize)]
pub struct Stmt {
    pub id: NodeId,
    pub span: Span,
    pub kind: StmtKind,
}
#[derive(Clone, Debug, Serialize)]
pub enum StmtKind {
    Declare {
        name: String,
        declared_type: Option<Type>,
        value: Expr,
    },
    Assign {
        target: Expr,
        operator: AssignOp,
        value: Expr,
    },
    Append {
        target: Expr,
        value: Expr,
    },
    Return(Expr),
    Break,
    Continue,
    Call(Expr),
    Function(Function),
    If {
        condition: Expr,
        then_body: Vec<Stmt>,
        else_body: Vec<Stmt>,
    },
    While {
        condition: Expr,
        body: Vec<Stmt>,
    },
    For {
        names: Vec<BindingName>,
        iteration: Iteration,
        body: Vec<Stmt>,
    },
}
#[derive(Clone, Debug, Serialize)]
pub struct Program {
    pub statements: Vec<Stmt>,
}
