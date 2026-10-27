//! Fixture structure and syntax checks use the native parser, without execution.
use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};
use zakc::ast::*;
use zakc::parser::parse;

fn corpus() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/conformance")
}

fn paths_with_extension(folder: &Path, extension: &str) -> Vec<PathBuf> {
    let mut paths: Vec<_> = fs::read_dir(folder)
        .unwrap()
        .map(|entry| entry.unwrap().path())
        .filter(|path| path.extension().is_some_and(|value| value == extension))
        .collect();
    paths.sort();
    paths
}

#[test]
fn fifteen_corpus_programs_have_matching_newline_terminated_outputs_and_parse() {
    let programs = paths_with_extension(&corpus(), "zak");
    let outputs = paths_with_extension(&corpus(), "expected");
    assert_eq!(programs.len(), 15);
    let stems = |paths: &[PathBuf]| {
        paths
            .iter()
            .map(|path| path.file_stem().unwrap().to_owned())
            .collect::<BTreeSet<_>>()
    };
    assert_eq!(stems(&programs), stems(&outputs));
    for path in programs {
        parse(&fs::read_to_string(&path).unwrap())
            .unwrap_or_else(|error| panic!("{}: {error:?}", path.display()));
        assert!(
            fs::read(path.with_extension("expected"))
                .unwrap()
                .ends_with(b"\n"),
            "{}: out(x) includes a trailing newline",
            path.display()
        );
    }
}

type Coverage = BTreeSet<&'static str>;
fn visit_type(ty: &Type, seen: &mut Coverage) {
    match ty {
        Type::Array(inner) => {
            seen.insert("arr_t");
            visit_type(inner, seen);
        }
        Type::Map(key, value) => {
            seen.insert("map_t");
            visit_type(key, seen);
            visit_type(value, seen);
        }
        _ => {}
    }
}
fn visit_expr(expr: &Expr, seen: &mut Coverage) {
    match &expr.kind {
        ExprKind::Literal(literal) => match literal {
            Literal::Real(_) => {
                seen.insert("float_lit");
            }
            Literal::Bool(true) => {
                seen.insert("true");
            }
            Literal::Bool(false) => {
                seen.insert("false");
            }
            Literal::Str(_) => {
                seen.insert("str_lit");
            }
            Literal::Int(_) => {}
        },
        ExprKind::Name(_) => {}
        ExprKind::Array(values) => {
            seen.insert("arr");
            for value in values {
                visit_expr(value, seen);
            }
        }
        ExprKind::Map(entries) => {
            seen.insert("map");
            for (key, value) in entries {
                visit_expr(key, seen);
                visit_expr(value, seen);
            }
        }
        ExprKind::Unary(op, value) => {
            seen.insert(match op {
                UnaryOp::Neg => "neg",
                UnaryOp::Not => "not_op",
                UnaryOp::Len => "length",
            });
            visit_expr(value, seen);
        }
        ExprKind::Binary(left, op, right) => {
            seen.insert(match op {
                BinaryOp::And => "and_op",
                BinaryOp::Or => "or_op",
                BinaryOp::In => "member",
                BinaryOp::Eq
                | BinaryOp::Ne
                | BinaryOp::Lt
                | BinaryOp::Le
                | BinaryOp::Gt
                | BinaryOp::Ge => "compare",
                BinaryOp::Add | BinaryOp::Sub | BinaryOp::Mul | BinaryOp::Div | BinaryOp::Mod => {
                    "binop"
                }
            });
            visit_expr(left, seen);
            visit_expr(right, seen);
        }
        ExprKind::Conditional {
            condition,
            then_value,
            else_value,
        } => {
            visit_expr(condition, seen);
            visit_expr(then_value, seen);
            visit_expr(else_value, seen);
        }
        ExprKind::Call { arguments, .. } => {
            seen.insert("call");
            for value in arguments {
                visit_expr(value, seen);
            }
        }
        ExprKind::Cast(ty, value) => {
            visit_type(ty, seen);
            visit_expr(value, seen);
        }
        ExprKind::Index(collection, index) => {
            seen.insert("index");
            visit_expr(collection, seen);
            visit_expr(index, seen);
        }
        ExprKind::Slice {
            collection,
            lower,
            upper,
        } => {
            seen.insert("slice");
            visit_expr(collection, seen);
            for value in [lower, upper].into_iter().flatten() {
                visit_expr(value, seen);
            }
        }
        ExprKind::Comprehension {
            value,
            iteration,
            condition,
            ..
        } => {
            visit_expr(value, seen);
            visit_iteration(iteration, seen);
            if let Some(condition) = condition {
                visit_expr(condition, seen);
            }
        }
    }
}
fn visit_iteration(iteration: &Iteration, seen: &mut Coverage) {
    visit_expr(&iteration.start, seen);
    if let Some(stop) = &iteration.stop {
        visit_expr(stop, seen);
    }
}
fn visit_statements(statements: &[Stmt], seen: &mut Coverage) {
    for statement in statements {
        match &statement.kind {
            StmtKind::Declare {
                declared_type,
                value,
                ..
            } => {
                seen.insert("decl");
                if let Some(ty) = declared_type {
                    visit_type(ty, seen);
                }
                visit_expr(value, seen);
            }
            StmtKind::Assign { target, value, .. } => {
                seen.insert("assign");
                visit_expr(target, seen);
                visit_expr(value, seen);
            }
            StmtKind::Append { target, value } => {
                seen.insert("push");
                visit_expr(target, seen);
                visit_expr(value, seen);
            }
            StmtKind::Return(value) => {
                seen.insert("ret");
                visit_expr(value, seen);
            }
            StmtKind::Break => {
                seen.insert("brk");
            }
            StmtKind::Continue => {
                seen.insert("cont");
            }
            StmtKind::Call(value) => visit_expr(value, seen),
            StmtKind::Function(function) => {
                seen.insert("fn");
                visit_type(&function.return_type, seen);
                for parameter in &function.parameters {
                    seen.insert("param");
                    visit_type(&parameter.ty, seen);
                }
                visit_statements(&function.body, seen);
            }
            StmtKind::If {
                condition,
                then_body,
                else_body,
            } => {
                seen.insert("if_");
                visit_expr(condition, seen);
                visit_statements(then_body, seen);
                visit_statements(else_body, seen);
            }
            StmtKind::While { condition, body } => {
                seen.insert("while_");
                visit_expr(condition, seen);
                visit_statements(body, seen);
            }
            StmtKind::For {
                iteration, body, ..
            } => {
                seen.insert("for_");
                visit_iteration(iteration, seen);
                visit_statements(body, seen);
            }
        }
    }
}

#[test]
fn corpus_covers_all_sd1_construct_families() {
    let mut seen = Coverage::new();
    for path in paths_with_extension(&corpus(), "zak") {
        let program = parse(&fs::read_to_string(path).unwrap()).unwrap();
        visit_statements(&program.statements, &mut seen);
    }
    let required: Coverage = [
        "decl",
        "assign",
        "binop",
        "neg",
        "float_lit",
        "compare",
        "true",
        "false",
        "and_op",
        "or_op",
        "not_op",
        "if_",
        "while_",
        "for_",
        "fn",
        "param",
        "ret",
        "call",
        "brk",
        "cont",
        "arr",
        "arr_t",
        "push",
        "index",
        "length",
        "str_lit",
        "slice",
        "map",
        "map_t",
        "member",
    ]
    .into_iter()
    .collect();
    assert_eq!(
        required.difference(&seen).copied().collect::<Vec<_>>(),
        Vec::<&str>::new(),
        "missing construct families"
    );
}

#[test]
fn all_benchmark_references_match_task_signatures() {
    let folder = Path::new(env!("CARGO_MANIFEST_DIR")).join("../zakbench/tasks");
    let mut task_paths: Vec<_> = fs::read_dir(folder)
        .unwrap()
        .map(|entry| entry.unwrap().path().join("task.json"))
        .filter(|path| path.is_file())
        .collect();
    task_paths.sort();
    assert!(!task_paths.is_empty(), "benchmark tasks must be present");
    for task_path in task_paths {
        let task: serde_json::Value =
            serde_json::from_str(&fs::read_to_string(&task_path).unwrap()).unwrap();
        let reference = task_path.with_file_name("reference.zak");
        let source = fs::read_to_string(&reference)
            .unwrap_or_else(|error| panic!("{} is required: {error}", reference.display()));
        let program =
            parse(&source).unwrap_or_else(|error| panic!("{}: {error:?}", reference.display()));
        let functions: Vec<_> = program
            .statements
            .iter()
            .filter_map(|statement| match &statement.kind {
                StmtKind::Function(function) => Some(function),
                _ => None,
            })
            .collect();
        assert_eq!(functions.len(), 1, "{}", reference.display());
        assert_eq!(
            functions[0].name,
            task["functionName"].as_str().unwrap(),
            "{}",
            reference.display()
        );
        let expected: Vec<_> = task["inputs"]
            .as_array()
            .unwrap()
            .iter()
            .map(|input| input["name"].as_str().unwrap())
            .collect();
        let actual: Vec<_> = functions[0]
            .parameters
            .iter()
            .map(|parameter| parameter.binding.name.as_str())
            .collect();
        assert_eq!(actual, expected, "{}", reference.display());
    }
}
