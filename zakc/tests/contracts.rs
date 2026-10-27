use zakc::ast::{Span, Type};
use zakc::{ErrorCode, ErrorContext, zak_check, zak_transpile};

#[test]
fn errors_distinguish_zak_source_from_rust_call_site() {
    let errors = zak_check("x:=1;\nout(unknown)").unwrap_err();
    assert_eq!(errors[0].code, ErrorCode::UndefinedName);
    let span = errors[0].span.unwrap();
    assert_eq!((span.line, span.col), (2, 5));
    assert!(!errors[0].sources.is_empty());
    assert!(errors[0].sources[0].location.file.ends_with("semantic.rs"));
}

#[test]
fn context_trait_preserves_origin_and_tracks_the_callers_exact_line() {
    let context = ("missing value", ErrorCode::InternalError);
    let line = line!() + 1;
    let error = None::<u32>.trace_ctx(context).unwrap_err();
    assert_eq!(error.sources[0].location.line, line);
    let again = Err::<u32, _>(error)
        .trace_ctx("outer operation")
        .unwrap_err();
    assert_eq!(again.sources[0].location.line, line);
    assert_eq!(again.sources.len(), 2);
    assert_eq!(again.sources[1].message.as_deref(), Some("outer operation"));
    let located = Err::<u32, _>(again).at(Span::point(3, 7)).unwrap_err();
    assert_eq!(located.span.unwrap().line, 3);
}

#[test]
fn typed_context_and_metadata_are_stable_after_moves() {
    let program = zak_check("a:[[I]]=[[]];i:=7/2;r:=7.0/2.0").unwrap();
    let moved = Box::new(program);
    assert!(
        moved
            .expression_types()
            .values()
            .any(|ty| ty == &Type::Real)
    );
    assert!(moved.expression_types().values().any(|ty| ty == &Type::Int));
    assert!(
        moved
            .expression_types()
            .values()
            .any(|ty| ty == &Type::array(Type::array(Type::Int)))
    );
}

#[test]
fn independent_failures_are_accumulated_with_exact_columns() {
    let errors = zak_check("out(x);out(y)").unwrap_err();
    assert_eq!(errors.len(), 2);
    assert_eq!(
        errors
            .iter()
            .map(|e| e.span.unwrap().col)
            .collect::<Vec<_>>(),
        [5, 12]
    );
}

#[test]
fn integer_and_real_division_emit_different_python_operators() {
    let generated = zak_transpile("i:=7/2;r:=7.0/2.0;out(i);out(r)").unwrap();
    assert!(generated.source.contains("//"));
    assert!(generated.source.contains(" / "));
    assert!(!generated.python_ast.is_empty());
    assert!(generated.source_map.iter().all(|entry| entry.zak.line > 0));
}

#[test]
fn syntax_and_end_of_file_have_real_source_locations() {
    let errors = zak_check("x:=1;\n?T{out(x)").unwrap_err();
    assert_eq!(errors[0].code, ErrorCode::SyntaxError);
    assert_eq!(errors[0].span.unwrap().line, 2);
}

#[test]
fn unsupported_syntax_fails_explicitly_and_compilation_never_executes() {
    let errors = zak_check("a:=[x~x:[1]]").unwrap_err();
    assert_eq!(errors[0].code, ErrorCode::UnsupportedFeature);
    assert!(zak_transpile("~T{}").is_ok());
}

#[test]
fn all_existing_programs_and_references_compile_to_real_python_ast() {
    let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .unwrap();
    let corpus = root.join("compiler/tests/conformance");
    let mut count = 0;
    for entry in std::fs::read_dir(corpus).unwrap() {
        let path = entry.unwrap().path();
        if path.extension().is_some_and(|ext| ext == "zak") {
            zak_transpile(&std::fs::read_to_string(&path).unwrap())
                .unwrap_or_else(|errors| panic!("{}: {errors:?}", path.display()));
            count += 1;
        }
    }
    assert_eq!(count, 15);
    let mut references = 0;
    for entry in std::fs::read_dir(root.join("zakbench/tasks")).unwrap() {
        let path = entry.unwrap().path().join("reference.zak");
        if path.is_file() {
            zak_transpile(&std::fs::read_to_string(&path).unwrap())
                .unwrap_or_else(|errors| panic!("{}: {errors:?}", path.display()));
            references += 1;
        }
    }
    assert_eq!(references, 10);
}

#[test]
fn unicode_columns_are_character_offsets_while_ranges_are_byte_offsets() {
    let errors = zak_check("out(\"é\");out(unknown)").unwrap_err();
    let span = errors[0].span.unwrap();
    assert_eq!((span.line, span.col, span.start), (1, 14, 14));
    assert_eq!(span.end - span.start, "unknown".len());
}

#[test]
fn outer_source_context_never_replaces_the_original_location() {
    let error = zak_check("\nout(missing)").unwrap_err().remove(0);
    let wrapped = Err::<(), _>(error).at(Span::point(99, 99)).unwrap_err();
    assert_eq!(
        (wrapped.span.unwrap().line, wrapped.span.unwrap().col),
        (2, 5)
    );
    assert_eq!(wrapped.code, ErrorCode::UndefinedName);
}

#[test]
fn io_errors_keep_the_attached_rust_call_site_and_message() {
    let operation = Err::<(), _>(std::io::Error::other("example"));
    let line = line!() + 1;
    let error = operation.trace_ctx("reading the source file").unwrap_err();
    assert_eq!(error.code, ErrorCode::IoError);
    let trace = error.sources.last().unwrap();
    assert_eq!(trace.location.line, line);
    assert_eq!(trace.message.as_deref(), Some("reading the source file"));
    let json = serde_json::to_value(error).unwrap();
    assert_eq!(json["code"], "IO_ERROR");
    assert!(json["error"].as_str().unwrap().contains("example"));
}

#[test]
fn display_and_variant_names_are_derived_from_the_enums() {
    use strum::IntoEnumIterator;
    use zakc::{ast::BinaryOp, semantic::Builtin};
    assert_eq!(Builtin::iter().count(), 15);
    for builtin in Builtin::iter() {
        assert_eq!(builtin.to_string().parse::<Builtin>().unwrap(), builtin);
    }
    for operator in BinaryOp::iter() {
        assert_eq!(operator.to_string().parse::<BinaryOp>().unwrap(), operator);
    }
    assert_eq!(
        Type::map(Type::Str, Type::array(Type::Int)).to_string(),
        "{S:[I]}"
    );
    assert_eq!(ErrorCode::TypeMismatch.to_string(), "TYPE_MISMATCH");
}

#[test]
fn complexity_limits_fail_without_stack_overflow() {
    for source in [
        format!("out({}1)", "-".repeat(2000)),
        format!("out({}1{})", "(".repeat(100), ")".repeat(100)),
        format!("out({})", vec!["1"; 200].join("+")),
    ] {
        assert_eq!(
            zak_check(&source).unwrap_err()[0].code,
            ErrorCode::ComplexityLimit
        );
    }
    assert!(zak_check(&format!("out({}1{})", "(".repeat(20), ")".repeat(20))).is_ok());
}

#[test]
fn integers_are_not_limited_to_rust_machine_word_size() {
    let source = "out(12345678901234567890123456789012345678901234567890);out(0007)";
    let generated = zak_transpile(source).unwrap();
    assert!(
        generated
            .source
            .contains("12345678901234567890123456789012345678901234567890")
    );
    assert!(generated.source.contains("print(7)"));
}

#[test]
fn serde_literal_errors_are_located_at_the_zak_literal() {
    let errors = zak_check("out(1);\nout(\"\\q\")").unwrap_err();
    assert_eq!(errors[0].code, ErrorCode::InvalidLiteral);
    let span = errors[0].span.unwrap();
    assert_eq!((span.line, span.col), (2, 5));
    assert!(errors[0].to_string().contains("INVALID_LITERAL at 2:5"));
}

#[test]
fn output_is_deterministic_even_though_analysis_uses_hash_maps() {
    let source = "x:=1;@f(n:I)I{x+=n;^x}out(f(2))";
    let first = zak_transpile(source).unwrap();
    zak_transpile("@unrelated()I{^0}").unwrap();
    let second = zak_transpile(source).unwrap();
    assert_eq!(first.source, second.source);
    assert!(first.source.contains("global _ZAK_v0"));
    assert_eq!(first.source_map.len(), second.source_map.len());
}

#[test]
fn staged_api_rejects_combined_asts_with_colliding_node_ids() {
    let mut left = zakc::parser::parse("x:=7;out(x/2)").unwrap();
    let right = zakc::parser::parse("y:=2.0;out(y/2.0)").unwrap();
    left.statements.extend(right.statements);
    let errors = left.check().unwrap_err();
    assert_eq!(errors[0].code.to_string(), "INVALID_AST");
}

#[test]
fn syntax_errors_preserve_byte_offsets_at_eof() {
    let source = "out(1);\nout(";
    let errors = zak_check(source).unwrap_err();
    let span = errors[0].span.unwrap();
    assert_eq!((span.line, span.col), (2, 5));
    assert_eq!((span.start, span.end), (source.len(), source.len()));
}

#[test]
fn long_delimiter_free_ternaries_return_a_diagnostic_instead_of_aborting() {
    use std::{
        io::Write,
        process::{Command, Stdio},
    };
    let mut child = Command::new("sh")
        .args([
            "-c",
            "ulimit -c 0; exec \"$@\"",
            "zakc-test",
            env!("CARGO_BIN_EXE_zakc"),
            "--json",
            "--emit",
            "check",
            "-",
        ])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    let source = format!("out({}0)", "T?1:".repeat(256));
    child
        .stdin
        .take()
        .unwrap()
        .write_all(source.as_bytes())
        .unwrap();
    let output = child.wait_with_output().unwrap();
    assert_eq!(
        output.status.code(),
        Some(1),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let json: serde_json::Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(json[0]["errors"][0]["code"], "COMPLEXITY_LIMIT");
}

#[test]
fn nested_brackets_parse_in_linear_time() {
    let started = std::time::Instant::now();
    let depth = 30;
    let arrays = format!("x:={}1{}", "[".repeat(depth), "]".repeat(depth));
    let indexes = format!(
        "a:[I]=[0];x:=a{}[0]{}",
        "[a".repeat(depth),
        "]".repeat(depth)
    );
    assert!(zak_check(&arrays).is_ok());
    assert!(zak_check(&indexes).is_ok());
    assert!(started.elapsed() < std::time::Duration::from_secs(2));
    let python = zak_transpile("a:[I]=[1,2,3];out(a[1:]);out(a[:2]);out(a[:]);out(a[0])")
        .unwrap()
        .source;
    assert!(python.contains("[1:]") && python.contains("[:2]") && python.contains("[:]"));
}
