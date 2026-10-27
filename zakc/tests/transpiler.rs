//! Native emission contracts. Snapshots intentionally record the Rust emitter's
//! helper prelude, parentheses and JSON string quoting, rather than ast.unparse.
use rustpython_parser::ast::{self as py, Expr, Stmt};
use zakc::{ErrorCode, zak_check, zak_transpile};

const ARITHMETIC: &str = "x:=7/2;y:=7.0/2.0;out(x);out(y)";
const FUNCTION: &str = "@f(n:I)I{total:=0;~i:0..n{?i%2==0{total+=i}}^total}out(f(4))";

#[test]
fn exact_snapshot_for_typed_arithmetic() {
    let output = zak_transpile(ARITHMETIC).unwrap();
    assert_eq!(output.source, include_str!("snapshots/arithmetic.py.txt"));
    let [
        Stmt::Import(import),
        Stmt::FunctionDef(helper),
        Stmt::Assign(integer),
        Stmt::Assign(real),
        Stmt::Expr(first),
        Stmt::Expr(second),
    ] = output.python_ast.as_slice()
    else {
        panic!("expected prelude, two assignments, and two output calls");
    };
    assert_eq!(import.names[0].name.as_str(), "builtins");
    assert_eq!(helper.name.as_str(), "_ZAK_join");
    for (assignment, expected) in [(integer, py::Operator::FloorDiv), (real, py::Operator::Div)] {
        let Expr::BinOp(binary) = assignment.value.as_ref() else {
            panic!("expected typed division")
        };
        assert_eq!(binary.op, expected);
        assert!(matches!(binary.left.as_ref(), Expr::Constant(_)));
        assert!(matches!(binary.right.as_ref(), Expr::Constant(_)));
    }
    for expression in [first, second] {
        let Expr::Call(call) = expression.value.as_ref() else {
            panic!("expected output call")
        };
        let Expr::Attribute(attribute) = call.func.as_ref() else {
            panic!("expected qualified builtin")
        };
        assert_eq!(attribute.attr.as_str(), "print");
        assert_eq!(call.args.len(), 1);
    }
}

#[test]
fn exact_snapshot_for_function_and_control_flow() {
    let output = zak_transpile(FUNCTION).unwrap();
    assert_eq!(output.source, include_str!("snapshots/function.py.txt"));
    let Stmt::FunctionDef(function) = &output.python_ast[2] else {
        panic!("expected user function")
    };
    assert_eq!(function.name.as_str(), "_ZAK_f0");
    assert_eq!(function.args.args.len(), 1);
    let [
        Stmt::Assign(_),
        Stmt::For(iteration),
        Stmt::Return(returned),
    ] = function.body.as_slice()
    else {
        panic!("expected accumulator, range loop, and return")
    };
    let Expr::Call(range) = iteration.iter.as_ref() else {
        panic!("expected range call")
    };
    assert_eq!(range.args.len(), 2);
    let Expr::Attribute(range_name) = range.func.as_ref() else {
        panic!("expected builtin range")
    };
    assert_eq!(range_name.attr.as_str(), "range");
    let [Stmt::If(condition)] = iteration.body.as_slice() else {
        panic!("expected conditional accumulation")
    };
    let Expr::Compare(comparison) = condition.test.as_ref() else {
        panic!("expected equality comparison")
    };
    assert_eq!(comparison.ops, [py::CmpOp::Eq]);
    let Expr::BinOp(modulo) = comparison.left.as_ref() else {
        panic!("expected modulo")
    };
    assert_eq!(modulo.op, py::Operator::Mod);
    let [Stmt::AugAssign(add)] = condition.body.as_slice() else {
        panic!("expected augmented accumulation")
    };
    assert_eq!(add.op, py::Operator::Add);
    assert!(matches!(returned.value.as_deref(), Some(Expr::Name(_))));
    assert!(matches!(output.python_ast.last(), Some(Stmt::Assign(_))));
}

#[test]
fn typed_augmented_division_and_short_circuit_are_real_ast_operators() {
    let output = zak_transpile("i:=7;i/=2;r:=7.0;r/=2.0;out(F&T);out(T|F);out(T?1:2)").unwrap();
    let Stmt::AugAssign(integer) = &output.python_ast[3] else {
        panic!("expected integer augmented division")
    };
    let Stmt::AugAssign(real) = &output.python_ast[5] else {
        panic!("expected real augmented division")
    };
    assert_eq!(integer.op, py::Operator::FloorDiv);
    assert_eq!(real.op, py::Operator::Div);
    for (index, expected) in [(6, py::BoolOp::And), (7, py::BoolOp::Or)] {
        let Stmt::Expr(expression) = &output.python_ast[index] else {
            panic!("expected output")
        };
        let Expr::Call(call) = expression.value.as_ref() else {
            panic!("expected call")
        };
        let Expr::BoolOp(boolean) = &call.args[0] else {
            panic!("expected short circuit operator")
        };
        assert_eq!(boolean.op, expected);
    }
    let Stmt::Expr(expression) = &output.python_ast[8] else {
        panic!("expected output")
    };
    let Expr::Call(call) = expression.value.as_ref() else {
        panic!("expected call")
    };
    assert!(matches!(call.args[0], Expr::IfExp(_)));
}

#[test]
fn repeated_emission_is_identical_and_independent() {
    let source = "x:=1;y:=2;@f()I{x+=y;y+=1;^x}a:=[1];out(f());out(a)";
    let checked = zak_check(source).unwrap();
    let first = checked.transpile().unwrap();
    zak_transpile("x:=\"unrelated\";out(x)").unwrap();
    let second = checked.transpile().unwrap();
    let fresh = zak_transpile(source).unwrap();
    assert_eq!(first.source, second.source);
    assert_eq!(first.source, fresh.source);
    assert_eq!(first.python_ast, second.python_ast);
    assert_eq!(first.python_ast, fresh.python_ast);
    assert_eq!(
        serde_json::to_value(&first.source_map).unwrap(),
        serde_json::to_value(&second.source_map).unwrap()
    );
}

#[test]
fn invalid_and_unsupported_programs_return_structured_source_errors() {
    for (source, code, location) in [
        ("\nout(missing)", ErrorCode::UndefinedName, (2, 5)),
        ("a:=[1];\na<<T", ErrorCode::TypeMismatch, (2, 4)),
        ("\na:=[x~x:[1]]", ErrorCode::UnsupportedFeature, (2, 4)),
    ] {
        let errors = zak_transpile(source).unwrap_err();
        let error = errors
            .iter()
            .find(|error| error.code == code)
            .expect("expected structured diagnostic code");
        let span = error.span.expect("Zak source coordinates");
        assert_eq!((span.line, span.col), location);
        assert!(span.start < span.end && span.end <= source.len());
        assert!(!error.sources.is_empty());
        let json = serde_json::to_value(error).unwrap();
        assert_eq!(json["code"], code.to_string());
        assert!(json["error"].is_string());
    }
}
