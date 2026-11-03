//! Public checking API and CLI contracts. Checking must never execute Zak code.
use serde_json::Value;
use std::{
    ffi::OsStr,
    path::PathBuf,
    process::{Command, Output},
    sync::atomic::{AtomicU64, Ordering},
};
use zakc::zak_check;

struct TempDir(PathBuf);
impl TempDir {
    fn new() -> Self {
        static NEXT: AtomicU64 = AtomicU64::new(0);
        loop {
            let path = std::env::temp_dir().join(format!(
                "zakc-check-{}-{}-{}",
                std::process::id(),
                std::time::SystemTime::now()
                    .duration_since(std::time::UNIX_EPOCH)
                    .unwrap()
                    .as_nanos(),
                NEXT.fetch_add(1, Ordering::Relaxed)
            ));
            match std::fs::create_dir(&path) {
                Ok(()) => return Self(path),
                Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
                Err(e) => panic!("create test directory: {e}"),
            }
        }
    }
    fn write(&self, name: &str, source: &str) -> PathBuf {
        let path = self.0.join(name);
        std::fs::write(&path, source).unwrap();
        path
    }
}
impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
fn command(args: impl IntoIterator<Item = impl AsRef<OsStr>>) -> Output {
    Command::new(env!("CARGO_BIN_EXE_zakc"))
        .args(["--emit", "check"])
        .args(args)
        .output()
        .unwrap()
}
fn stdout(result: &Output) -> String {
    String::from_utf8(result.stdout.clone()).unwrap()
}
fn stderr(result: &Output) -> String {
    String::from_utf8(result.stderr.clone()).unwrap()
}

#[test]
fn public_check_accepts_entire_corpus() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let mut paths: Vec<_> = std::fs::read_dir(root.join("tests/conformance"))
        .unwrap()
        .map(|e| e.unwrap().path())
        .filter(|p| p.extension().is_some_and(|e| e == "zak"))
        .collect();
    assert!(!paths.is_empty());
    let mut references = vec![];
    for entry in std::fs::read_dir(root.parent().unwrap().join("zakbench/tasks")).unwrap() {
        let dir = entry.unwrap().path();
        if dir.join("task.json").is_file() {
            let path = dir.join("reference.zak");
            assert!(path.is_file(), "{}", path.display());
            references.push(path);
        }
    }
    assert!(
        !references.is_empty(),
        "benchmark references must be present"
    );
    paths.extend(references);
    paths.sort();
    for path in paths {
        let result = zak_check(&std::fs::read_to_string(&path).unwrap());
        assert!(result.is_ok(), "{}: {:?}", path.display(), result.err());
        let _syntax: &zakc::ast::Program = result.unwrap().syntax();
    }
}

#[test]
fn public_check_returns_located_structured_errors() {
    let data: Value = serde_json::from_str(include_str!("cases/compile.json")).unwrap();
    for case in data["test_compile_returns_located_errors"]
        .as_array()
        .unwrap()
    {
        let source = case[0].as_str().unwrap();
        let errors = zak_check(source).unwrap_err();
        assert!(
            errors
                .iter()
                .any(|e| e.code.to_string() == case[1].as_str().unwrap()),
            "{source}: {errors:?}"
        );
        for error in errors {
            let span = error.span.unwrap();
            assert!(span.line > 0 && span.col > 0);
            let value = serde_json::to_value(&error).unwrap();
            assert!(value["error"].as_str().is_some_and(|s| !s.is_empty()));
            assert!(!value["sources"].as_array().unwrap().is_empty());
        }
    }
}

#[test]
fn empty_program_syntax_position_and_complexity_limit() {
    assert!(zak_check(" \n").unwrap().syntax().statements.is_empty());
    let errors = zak_check("x:=1;\ny:=?").unwrap_err();
    let span = errors[0].span.unwrap();
    assert_eq!(
        (span.line, span.col, errors[0].code.to_string()),
        (2, 4, "SYNTAX_ERROR".into())
    );
    let errors = zak_check(&format!("out({}1)", "-".repeat(2000))).unwrap_err();
    assert_eq!(errors[0].code.to_string(), "COMPLEXITY_LIMIT");
}

#[test]
fn cli_recursively_checks_directories_without_execution() {
    let dir = TempDir::new();
    let nested = dir.0.join("nested");
    std::fs::create_dir(&nested).unwrap();
    let valid = nested.join("valid.zak");
    std::fs::write(&valid, "out(\"THIS MUST NOT EXECUTE\")").unwrap();
    dir.write("ignored.txt", "out(missing)");
    let result = command([&dir.0]);
    assert!(result.status.success(), "{}", stderr(&result));
    assert!(stdout(&result).contains(&format!("{}: OK", valid.display())));
    assert!(!stdout(&result).contains("THIS MUST NOT EXECUTE"));
}

#[test]
fn cli_checks_all_files_and_reports_errors_on_stderr() {
    let dir = TempDir::new();
    let good = dir.write("good.zak", "out(1)");
    let bad = dir.write("bad.zak", "out(missing)");
    let result = command([&bad, &good]);
    assert_eq!(result.status.code(), Some(1));
    assert!(
        stderr(&result).contains(&format!("{}:UNDEFINED_NAME at 1:5:", bad.display())),
        "{}",
        stderr(&result)
    );
    assert!(stdout(&result).contains(&format!("{}: OK", good.display())));
}

#[test]
fn cli_json_preserves_source_locations_and_rust_traces() {
    let dir = TempDir::new();
    let bad = dir.write("bad.zak", "out(missing)");
    let good = dir.write("good.zak", "out(1)");
    let result = command([OsStr::new("--json"), bad.as_os_str(), good.as_os_str()]);
    assert_eq!(result.status.code(), Some(1));
    assert!(result.stderr.is_empty());
    let entries: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(entries.as_array().unwrap().len(), 2);
    assert_eq!(entries[0]["path"], bad.to_str().unwrap());
    assert_eq!(entries[0]["ok"], false);
    let error = &entries[0]["errors"][0];
    assert_eq!(error["code"], "UNDEFINED_NAME");
    assert_eq!(error["span"]["line"], 1);
    assert_eq!(error["span"]["col"], 5);
    let traces = error["sources"].as_array().unwrap();
    assert!(!traces.is_empty());
    for trace in traces {
        assert!(
            trace["location"]["file"]
                .as_str()
                .is_some_and(|s| !s.is_empty())
        );
        assert!(trace["location"]["line"].as_u64().unwrap() > 0);
        assert!(trace["location"]["column"].as_u64().unwrap() > 0);
    }
    assert_eq!(entries[1]["ok"], true);
    assert_eq!(entries[1]["output"], "");
    assert_eq!(entries[1]["errors"], serde_json::json!([]));
}

#[test]
fn cli_json_io_error_and_empty_directory() {
    let dir = TempDir::new();
    let missing = dir.0.join("missing.zak");
    let result = command([OsStr::new("--json"), missing.as_os_str()]);
    assert_eq!(result.status.code(), Some(1));
    let entries: Value = serde_json::from_slice(&result.stdout).unwrap();
    assert_eq!(entries.as_array().unwrap().len(), 1);
    assert_eq!(entries[0]["path"], missing.to_str().unwrap());
    assert_eq!(entries[0]["ok"], false);
    assert_eq!(entries[0]["errors"][0]["code"], "IO_ERROR");
    assert!(entries[0]["errors"][0]["span"].is_null());
    assert!(
        !entries[0]["errors"][0]["sources"]
            .as_array()
            .unwrap()
            .is_empty()
    );
    let result = command([&dir.0]);
    assert_eq!(result.status.code(), Some(2));
    assert!(stderr(&result).contains("No .zak files"));
}
