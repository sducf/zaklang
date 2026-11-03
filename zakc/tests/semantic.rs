//! Native ports of the legacy static-semantic and contextual-inference contracts.
use serde_json::Value;
use std::path::PathBuf;
use zakc::{CompilerError, parser};

fn cases() -> Value {
    serde_json::from_str(include_str!("cases/semantic.json")).unwrap()
}

fn assert_located(errors: &[CompilerError]) {
    assert!(!errors.is_empty());
    for error in errors {
        let span = error.span.expect("source diagnostic has a location");
        assert!(span.line > 0 && span.col > 0, "{error:?}");
        assert!(!error.error.to_string().is_empty());
        assert!(!error.sources.is_empty(), "diagnostic retains Rust traces");
    }
}

#[test]
fn corpus_passes_ast_semantic_check() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut paths: Vec<_> = std::fs::read_dir(root.join("tests/conformance"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "zak"))
        .collect();
    assert!(!paths.is_empty(), "conformance fixtures must be present");
    let tasks = root.parent().unwrap().join("zakbench/tasks");
    let mut references = vec![];
    for entry in std::fs::read_dir(tasks).unwrap() {
        let dir = entry.unwrap().path();
        if dir.join("task.json").is_file() {
            let reference = dir.join("reference.zak");
            assert!(reference.is_file(), "{}", dir.display());
            references.push(reference);
        }
    }
    assert!(
        !references.is_empty(),
        "benchmark references must be present"
    );
    paths.extend(references);
    paths.sort();
    for path in paths {
        let source = std::fs::read_to_string(&path).unwrap();
        let result = parser::parse(&source)
            .unwrap_or_else(|e| panic!("{}: {e}", path.display()))
            .check();
        assert!(result.is_ok(), "{}: {:?}", path.display(), result.err());
    }
}

#[test]
fn valid_semantics_and_contextual_empty_array_inference() {
    let data = cases();
    for group in [
        "test_valid_semantics",
        "test_empty_arrays_use_context_from_operators_and_builtin_signatures",
    ] {
        for source in data[group].as_array().unwrap() {
            let source = source.as_str().unwrap();
            let result = parser::parse(source).unwrap().check();
            assert!(result.is_ok(), "{source}: {:?}", result.err());
        }
    }
}

#[test]
fn invalid_semantics_preserve_codes_and_source_locations() {
    let data = cases();
    for case in data["test_rejects_invalid_semantics"].as_array().unwrap() {
        let source = case[0].as_str().unwrap();
        let code = case[1].as_str().unwrap();
        let errors = parser::parse(source).unwrap().check().unwrap_err();
        assert_located(&errors);
        assert!(
            errors.iter().any(|e| e.code.to_string() == code),
            "{source}: {errors:?}"
        );
    }
    for source in data["test_contextual_inference_preserves_strict_element_types"]
        .as_array()
        .unwrap()
    {
        let source = source.as_str().unwrap();
        let errors = parser::parse(source).unwrap().check().unwrap_err();
        assert_located(&errors);
        assert!(
            errors.iter().any(|e| e.code.to_string() == "TYPE_MISMATCH"),
            "{source}: {errors:?}"
        );
    }
}

#[test]
fn undefined_expression_location_and_independent_statement_recovery() {
    let errors = parser::parse("x:=1;\nout(unknown)")
        .unwrap()
        .check()
        .unwrap_err();
    let span = errors[0].span.unwrap();
    assert_eq!(
        (span.line, span.col, errors[0].code.to_string()),
        (2, 5, "UNDEFINED_NAME".into())
    );
    let errors = parser::parse("out(x);out(y)").unwrap().check().unwrap_err();
    assert_eq!(errors.len(), 2);
    assert_eq!(
        errors
            .iter()
            .map(|e| e.span.unwrap().col)
            .collect::<Vec<_>>(),
        [5, 12]
    );
}
