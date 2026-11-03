//! Public syntax contracts, independent of the parser implementation.
use zakc::ast::{AssignOp, BinaryOp, Expr, ExprKind, Literal, StmtKind, Type};
use zakc::parser::parse;

fn declaration_value(statement: &zakc::ast::Stmt) -> &Expr {
    let StmtKind::Declare { value, .. } = &statement.kind else {
        panic!("expected declaration: {statement:?}");
    };
    value
}

fn integer(value: Option<&Expr>) -> Option<&str> {
    value.map(|value| {
        let ExprKind::Literal(Literal::Int(number)) = &value.kind else {
            panic!("expected integer literal: {value:?}");
        };
        number.as_str()
    })
}

#[test]
fn precedence_and_source_locations() {
    let source = "\nx:=2+3*4;out(x)";
    let program = parse(source).unwrap();
    let declaration = &program.statements[0];
    assert_eq!((declaration.span.line, declaration.span.col), (2, 1));
    assert_eq!(
        &source[declaration.span.start..declaration.span.end],
        "x:=2+3*4"
    );
    let addition = declaration_value(declaration);
    let ExprKind::Binary(left, BinaryOp::Add, right) = &addition.kind else {
        panic!("expected addition: {addition:?}");
    };
    assert_eq!(integer(Some(left)), Some("2"));
    let ExprKind::Binary(left, BinaryOp::Mul, right) = &right.kind else {
        panic!("expected multiplication: {right:?}");
    };
    assert_eq!(integer(Some(left)), Some("3"));
    assert_eq!(integer(Some(right)), Some("4"));
}

#[test]
fn slices_preserve_missing_endpoints() {
    for (source, lower, upper) in [
        ("x:=a[:2]", None, Some("2")),
        ("x:=a[1:]", Some("1"), None),
        ("x:=a[:]", None, None),
    ] {
        let program = parse(source).unwrap();
        let ExprKind::Slice {
            collection,
            lower: actual_lower,
            upper: actual_upper,
        } = &declaration_value(&program.statements[0]).kind
        else {
            panic!("expected slice for {source}")
        };
        assert!(matches!(&collection.kind, ExprKind::Name(name) if name == "a"));
        assert_eq!(integer(actual_lower.as_deref()), lower, "{source}");
        assert_eq!(integer(actual_upper.as_deref()), upper, "{source}");
    }
}

#[test]
fn grammar_header_function_examples_have_explicit_ast() {
    let examples = [
        (
            "@fib(n:I)I{?n<2{^n}^fib(n-1)+fib(n-2)}",
            "fib",
            "n",
            Type::Int,
        ),
        (
            "@cnt(s:S){S:I}{m:{S:I}={};~w:spl(s,\" \"){?w@m{m[w]+=1}:{m[w]=1}}^m}",
            "cnt",
            "s",
            Type::map(Type::Str, Type::Int),
        ),
        (
            "@ok(o:[{S:I}],lim:I)[B]{^[x[\"q\"]>0&x[\"p\"]<=lim~x:o]}",
            "ok",
            "o",
            Type::array(Type::Bool),
        ),
        (
            "@bs(a:[I],t:I)I{l:=0;h:=#a-1;~l<=h{m:=(l+h)/2;?a[m]==t{^m}:?a[m]<t{l=m+1}:{h=m-1}}^-1}",
            "bs",
            "a",
            Type::Int,
        ),
    ];
    for (source, name, parameter, return_type) in examples {
        let program = parse(source).unwrap();
        let StmtKind::Function(function) = &program.statements[0].kind else {
            panic!("expected function: {source}");
        };
        assert_eq!(function.name, name);
        assert_eq!(function.parameters[0].binding.name, parameter);
        assert_eq!(function.return_type, return_type);
        if name == "ok" {
            let StmtKind::Return(value) = &function.body[0].kind else {
                panic!("expected return");
            };
            assert!(matches!(value.kind, ExprKind::Comprehension { .. }));
        }
    }
}

#[test]
fn empty_literals_and_nested_types() {
    let program = parse("a:[[I]]=[[]];m:{S:I}={}").unwrap();
    let StmtKind::Declare {
        declared_type,
        value,
        ..
    } = &program.statements[0].kind
    else {
        panic!("expected array declaration");
    };
    assert_eq!(
        declared_type.as_ref(),
        Some(&Type::array(Type::array(Type::Int)))
    );
    let ExprKind::Array(elements) = &value.kind else {
        panic!("expected array")
    };
    assert_eq!(elements.len(), 1);
    assert!(matches!(&elements[0].kind, ExprKind::Array(nested) if nested.is_empty()));
    let StmtKind::Declare {
        declared_type,
        value,
        ..
    } = &program.statements[1].kind
    else {
        panic!("expected map declaration");
    };
    assert_eq!(
        declared_type.as_ref(),
        Some(&Type::map(Type::Str, Type::Int))
    );
    assert!(matches!(&value.kind, ExprKind::Map(entries) if entries.is_empty()));
}

#[test]
fn assignment_operator_and_iteration_names() {
    let program = parse("m[k]+=1;~k,v:m{out(v)}").unwrap();
    let StmtKind::Assign {
        target, operator, ..
    } = &program.statements[0].kind
    else {
        panic!("expected assignment");
    };
    assert_eq!(*operator, AssignOp::Augmented(BinaryOp::Add));
    assert!(matches!(target.kind, ExprKind::Index(..)));
    let StmtKind::For { names, .. } = &program.statements[1].kind else {
        panic!("expected for loop");
    };
    assert_eq!(
        names
            .iter()
            .map(|binding| binding.name.as_str())
            .collect::<Vec<_>>(),
        ["k", "v"]
    );
}
