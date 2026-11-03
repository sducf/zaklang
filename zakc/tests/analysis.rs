//! Checked-program metadata contracts formerly exercised through Python.
use zakc::ast::{Expr, ExprKind, Stmt, StmtKind, Type};
use zakc::{ErrorCode, parser::parse};

fn declaration_value(statement: &Stmt) -> &Expr {
    let StmtKind::Declare { value, .. } = &statement.kind else {
        panic!("expected declaration: {statement:?}");
    };
    value
}

#[test]
fn analysis_distinguishes_integer_and_real_division() {
    let checked = parse("i:=7/2;r:=7.0/2.0").unwrap().check().unwrap();
    let statements = &checked.syntax().statements;
    assert_eq!(
        checked
            .expression_types()
            .get(&declaration_value(&statements[0]).id),
        Some(&Type::Int)
    );
    assert_eq!(
        checked
            .expression_types()
            .get(&declaration_value(&statements[1]).id),
        Some(&Type::Real)
    );
}

#[test]
fn contextual_nested_empty_array_type_is_retained() {
    let checked = parse("a:[[I]]=[[]]").unwrap().check().unwrap();
    let value = declaration_value(&checked.syntax().statements[0]);
    let ExprKind::Array(elements) = &value.kind else {
        panic!("expected array")
    };
    assert_eq!(
        checked.expression_types().get(&value.id),
        Some(&Type::array(Type::array(Type::Int)))
    );
    assert_eq!(
        checked.expression_types().get(&elements[0].id),
        Some(&Type::array(Type::Int))
    );
}

#[test]
fn assignment_target_collection_and_void_call_types() {
    let checked = parse("a:=[1];a[0]/=2;out(a)").unwrap().check().unwrap();
    let StmtKind::Assign { target, .. } = &checked.syntax().statements[1].kind else {
        panic!("expected assignment");
    };
    let ExprKind::Index(collection, _) = &target.kind else {
        panic!("expected index")
    };
    assert_eq!(checked.expression_types().get(&target.id), Some(&Type::Int));
    assert_eq!(
        checked.expression_types().get(&collection.id),
        Some(&Type::array(Type::Int))
    );
    let StmtKind::Call(call) = &checked.syntax().statements[2].kind else {
        panic!("expected call")
    };
    assert_eq!(checked.expression_types().get(&call.id), Some(&Type::Void));
}

#[test]
fn checking_accumulates_diagnostics_in_source_order() {
    let errors = parse("out(x);a:I=T").unwrap().check().unwrap_err();
    assert_eq!(
        errors.iter().map(|error| error.code).collect::<Vec<_>>(),
        [ErrorCode::UndefinedName, ErrorCode::TypeMismatch]
    );
}

#[test]
fn metadata_is_independent_between_checked_programs() {
    let first = parse("x:=1").unwrap().check().unwrap();
    let first_types = first.expression_types().clone();
    let first_id = declaration_value(&first.syntax().statements[0]).id;
    let second = parse("x:=1.0").unwrap().check().unwrap();
    let second_id = declaration_value(&second.syntax().statements[0]).id;
    // IDs belong to each program; independent parses may reuse the same number.
    assert_eq!(first.expression_types(), &first_types);
    assert_eq!(first.expression_types().get(&first_id), Some(&Type::Int));
    assert_eq!(second.expression_types().get(&second_id), Some(&Type::Real));
    let third = parse("x:=[[1]]").unwrap().check().unwrap();
    let third_id = declaration_value(&third.syntax().statements[0]).id;
    assert_eq!(
        third.expression_types().get(&third_id),
        Some(&Type::array(Type::array(Type::Int)))
    );
    assert_eq!(second.expression_types().get(&second_id), Some(&Type::Real));
    assert_eq!(first.expression_types(), &first_types);
}
