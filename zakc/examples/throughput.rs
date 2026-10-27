//! In-process corpus throughput; excludes startup, file IO, and execution.
use std::{hint::black_box, path::Path, time::Instant};
use zakc::zak_transpile;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let root = Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .ok_or("missing repository root")?;

    let mut paths = vec![];

    for entry in std::fs::read_dir(root.join("zakc/tests/conformance"))? {
        let path = entry?.path();

        if path.extension().is_some_and(|ext| ext == "zak") {
            paths.push(path);
        }
    }

    for entry in std::fs::read_dir(root.join("zakbench/tasks"))? {
        let path = entry?.path().join("reference.zak");

        if path.is_file() {
            paths.push(path);
        }
    }

    paths.sort();

    let sources = paths
        .iter()
        .map(std::fs::read_to_string)
        .collect::<Result<Vec<_>, _>>()?;

    let rounds: usize = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "200".into())
        .parse()?;

    for source in &sources {
        zak_transpile(source).map_err(|e| format!("{e:?}"))?;
    }

    let start = Instant::now();

    for _ in 0..rounds {
        for source in &sources {
            black_box(zak_transpile(black_box(source)).map_err(|e| format!("{e:?}"))?);
        }
    }

    let elapsed = start.elapsed().as_secs_f64();

    println!(
        "{}",
        serde_json::json!({"implementation":if cfg!(debug_assertions) { "Rust (debug)" } else { "Rust (release)" },"programs":sources.len(),
        "rounds":rounds,"compilations":rounds*sources.len(),"seconds":elapsed,
        "microseconds_per_program":elapsed*1e6/(rounds*sources.len()) as f64})
    );
    Ok(())
}
