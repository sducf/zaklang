use clap::{Parser, ValueEnum};
use std::{
    io::{self, Read},
    path::{Path, PathBuf},
    process::ExitCode,
};
use zakc::{
    compile,
    error::{CompilerError, ErrorContext},
    transpiler::transpile,
};

#[derive(Clone, Copy, Debug, ValueEnum)]
enum Emit {
    Python,
    ZakAst,
    PythonAst,
    Check,
}
#[derive(Parser)]
#[command(
    name = "zakc",
    about = "Native Rust Zak compiler experiment; never executes generated code"
)]
struct Args {
    /// Zak files/directories, or '-' for stdin.
    #[arg(required = true)]
    paths: Vec<PathBuf>,
    #[arg(long, value_enum, default_value = "python")]
    emit: Emit,
    /// JSON results on stdout, including structured source diagnostics and Rust traces.
    #[arg(long)]
    json: bool,
}

fn load(path: &Path) -> Result<String, CompilerError> {
    if path == Path::new("-") {
        let mut source = String::new();
        io::stdin()
            .read_to_string(&mut source)
            .trace_ctx("reading stdin")?;
        Ok(source)
    } else {
        std::fs::read_to_string(path).trace_ctx(format!("reading {}", path.display()))
    }
}
fn collect(path: &Path, files: &mut Vec<PathBuf>) -> Result<(), CompilerError> {
    if path.is_dir() {
        let mut entries = std::fs::read_dir(path)
            .trace()?
            .collect::<Result<Vec<_>, _>>()
            .trace()?;
        entries.sort_by_key(|entry| entry.path());
        for entry in entries {
            let path = entry.path();
            if path.is_dir() || path.extension().is_some_and(|ext| ext == "zak") {
                collect(&path, files)?;
            }
        }
    } else {
        files.push(path.to_owned());
    }
    Ok(())
}
fn main() -> ExitCode {
    let args = Args::parse();
    let mut files = vec![];
    for path in &args.paths {
        if let Err(error) = collect(path, &mut files) {
            eprintln!("{error}");
            return ExitCode::FAILURE;
        }
    }
    if files.is_empty() {
        eprintln!("No .zak files found");
        return ExitCode::from(2);
    }
    let mut failed = false;
    let mut reports = vec![];
    for path in files {
        let outcome = (|| {
            let source = load(&path).map_err(|e| vec![e])?;
            let checked = compile(&source)?;
            let output = match args.emit {
                Emit::ZakAst => serde_json::to_string_pretty(checked.syntax())
                    .trace()
                    .map_err(|e| vec![e])?,
                Emit::Check => String::new(),
                Emit::Python | Emit::PythonAst => {
                    let generated = transpile(&checked).map_err(|e| vec![e])?;
                    if matches!(args.emit, Emit::PythonAst) {
                        format!("{:#?}", generated.python_ast)
                    } else {
                        generated.source
                    }
                }
            };
            Ok::<_, Vec<CompilerError>>(output)
        })();
        match outcome {
            Ok(output) => {
                if args.json {
                    reports.push(
                        serde_json::json!({"path":path,"ok":true,"output":output,"errors":[]}),
                    );
                } else if matches!(args.emit, Emit::Check) {
                    println!("{}: OK", path.display());
                } else {
                    print!("{output}");
                }
            }
            Err(errors) => {
                failed = true;
                if args.json {
                    reports.push(serde_json::json!({"path":path,"ok":false,"errors":errors}));
                } else {
                    for error in errors {
                        eprintln!("{}:{error}", path.display());
                    }
                }
            }
        }
    }
    if args.json {
        println!("{}", serde_json::Value::Array(reports));
    }
    if failed {
        ExitCode::FAILURE
    } else {
        ExitCode::SUCCESS
    }
}
