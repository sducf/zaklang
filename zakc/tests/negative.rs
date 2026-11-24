use serde::Deserialize;
use std::{fs, path::PathBuf};
use zakc::zak_check;

#[derive(Debug, Deserialize)]
struct ExpectedError {
    code: String,
    line: usize,
    col: usize,
}

#[test]
fn negative_compile_suite() {
    let directory = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/negative");

    let mut programs: Vec<_> = fs::read_dir(&directory)
        .expect("negative fixture directory exists")
        .map(|entry| entry.unwrap().path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "zak"))
        .collect();

    programs.sort();

    // SD-55 requires at least 30 invalid Zak programs.
    assert!(
        programs.len() >= 30,
        "Expected at least 30 negative test cases, found {}",
        programs.len()
    );

    for program in &programs {
        // Read the invalid Zak source program.
        let source = fs::read_to_string(program)
            .unwrap_or_else(|_| panic!("Cannot read {}", program.display()));

        // Read the corresponding expected diagnostic.
        let expected_path = program.with_extension("error.json");

        let expected: ExpectedError = serde_json::from_str(
            &fs::read_to_string(&expected_path)
                .unwrap_or_else(|_| panic!("Missing expectation: {}", expected_path.display())),
        )
        .unwrap_or_else(|_| panic!("Invalid JSON expectation: {}", expected_path.display()));

        // Every negative fixture must fail compilation.
        let errors = zak_check(&source).unwrap_err();

        // Each fixture must produce exactly one diagnostic.
        assert_eq!(
            errors.len(),
            1,
            "{}: expected exactly one diagnostic, received {errors:?}",
            program.display()
        );

        let error = &errors[0];

        // Validate the exact compiler error code.
        assert_eq!(
            error.code.to_string(),
            expected.code,
            "{}: incorrect error code",
            program.display()
        );

        // Every diagnostic must include a source location.
        let span = error.span.expect("diagnostic must include source location");

        // Validate the exact line and column.
        assert_eq!(
            (span.line, span.col),
            (expected.line, expected.col),
            "{}: incorrect error location",
            program.display()
        );

        // Validate that the diagnostic contains a message.
        assert!(
            !error.error.to_string().is_empty(),
            "{}: diagnostic message is empty",
            program.display()
        );

        // Validate that source context is included.
        assert!(
            !error.sources.is_empty(),
            "{}: diagnostic is missing source context",
            program.display()
        );
    }
}
