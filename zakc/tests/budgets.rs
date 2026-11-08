//! SD-71: the `?` budget bounds how deeply conditionals chain, not how many a
//! program contains. pest recurses once per chained `?` (elif chains and nested
//! or chained ternaries), so the parser pre-check must never undercount that.
use zakc::{CompilerError, zak_check, zak_transpile};

const CHAIN_MESSAGE: &str = "Conditional chain depth exceeds 128";

fn elif_chain(depth: usize, innermost: &str) -> String {
    let mut source = String::from("x:=1;?x==0{out(0)}");
    for index in 1..depth {
        let body = if index + 1 == depth {
            innermost.to_owned()
        } else {
            format!("out({index})")
        };
        source.push_str(&format!(":?x=={index}{{{body}}}"));
    }
    source
}

fn ternary_chain(depth: usize) -> String {
    format!("out({}0)", "T?1:".repeat(depth))
}

/// Rejected by the parser pre-check (chain depth or delimiter nesting), before pest runs.
fn pre_parse_rejection(errors: &[CompilerError]) -> bool {
    chain_rejection(errors)
        || errors.iter().any(|error| {
            error.code.to_string() == "COMPLEXITY_LIMIT"
                && error.error.to_string() == "Prototype source/nesting budget exceeded"
        })
}

fn chain_rejection(errors: &[CompilerError]) -> bool {
    errors.iter().any(|error| {
        error.code.to_string() == "COMPLEXITY_LIMIT" && error.error.to_string() == CHAIN_MESSAGE
    })
}

#[test]
fn independent_conditionals_are_not_limited_by_their_total_count() {
    // 600 functions, each with an elif, a ternary, and a second if: 2,400 markers.
    let functions: String = (0..600)
        .map(|i| format!("@f{i}(n:I)I{{?n>0{{^1}}:?n<0{{^-1}}x:=n==0?0:1;?x==0{{^0}}^x}}"))
        .collect();
    zak_transpile(&functions).unwrap();

    // Top-level ifs that follow each other without `;`, then `;`-separated ternaries.
    let script = format!(
        "x:=1;y:=0;{}{}out(x+y)",
        "?x>0{x+=1}".repeat(300),
        "y=x>2?1:0;".repeat(300)
    );
    zak_transpile(&script).unwrap();

    // Ternaries in separate collection items and call arguments.
    let items = vec!["x>0?1:0"; 300].join(",");
    zak_transpile(&format!(
        "x:=1;a:=[{items}];out(max(x>0?1:0,x<0?1:0));out(#a)"
    ))
    .unwrap();

    // If/else statements that follow each other inside one block.
    let block = format!("@g(n:I)I{{t:=0;{}^t}}", "?n>t{t+=1}:{t-=1}".repeat(300));
    zak_transpile(&block).unwrap();
}

#[test]
fn chains_deeper_than_128_are_rejected_before_parsing() {
    for source in [
        elif_chain(129, "out(0)"),
        ternary_chain(129),
        ternary_chain(5000),
    ] {
        let errors = zak_check(&source).unwrap_err();
        assert!(chain_rejection(&errors), "{errors:?}");
    }
}

#[test]
fn chain_depth_is_summed_across_nested_delimiters() {
    // 100 elif levels plus a 29-deep ternary inside the innermost block.
    let inner = format!("out({}0)", "T?1:".repeat(29));
    let errors = zak_check(&elif_chain(100, &inner)).unwrap_err();
    assert!(chain_rejection(&errors), "{errors:?}");

    // Ternaries nested through parentheses also add up.
    let nested = format!("out({}0{})", "(T?1:".repeat(129), ")".repeat(129));
    assert!(zak_check(&nested).is_err());
}

#[test]
fn map_literals_cannot_end_a_ternary_chain() {
    // A map literal's `}` is not a block end, so the chain must keep counting.
    for source in [
        format!("x:={}0", "T?{1:1}[1]:".repeat(200)),
        format!("x:={}{{1:1}}", "{1:1}?".repeat(200)),
        format!("x:={}0", "T?{1:1}:{2:2}?1:".repeat(100)),
    ] {
        let errors = zak_check(&source).unwrap_err();
        assert!(chain_rejection(&errors), "{source:.60}: {errors:?}");
    }
}

#[test]
fn chains_near_the_limit_compile_or_fail_cleanly_on_a_small_stack() {
    let handle = std::thread::Builder::new()
        .stack_size(256 * 1024)
        .spawn(|| {
            for depth in 1..=140 {
                for source in [elif_chain(depth, "out(0)"), ternary_chain(depth)] {
                    match zak_transpile(&source) {
                        Ok(_) => assert!(depth <= 128, "depth {depth} accepted"),
                        Err(errors) => assert!(
                            errors
                                .iter()
                                .all(|e| e.code.to_string() == "COMPLEXITY_LIMIT"),
                            "depth {depth}: {errors:?}"
                        ),
                    }
                }
            }
            // Realistic chains well under the limit always compile.
            zak_transpile(&elif_chain(100, "out(0)")).unwrap();
            zak_transpile(&ternary_chain(100)).unwrap();
        })
        .unwrap();
    handle.join().unwrap();
}

#[test]
fn random_deep_chains_are_always_rejected_and_never_overflow() {
    // Each fragment extends the open chain by exactly one `?`; several hide the
    // chain behind map literals, indexing, or parentheses. Any mix deeper than
    // 128 must be rejected by the pre-check. Without the budget, pest segfaults
    // from about 5,000 levels, so depths up to 8,128 make an undercount crash.
    const EXPRESSION: &[(&str, &str)] = &[
        ("T?1:", ""),
        ("T?{1:1}[1]:", ""),
        ("{1:1}?", ""),
        ("T?{1:1}:{2:2}?1:", ""),
        ("(T?", ")"),
        ("[T?", "]"),
        ("x?[1]:", ""),
        ("T?\"s\":", ""),
    ];
    let handle = std::thread::Builder::new()
        .stack_size(256 * 1024)
        .spawn(|| {
            let mut state: u64 = 0x5eed;
            let mut next = |bound: usize| {
                state = state
                    .wrapping_mul(6364136223846793005)
                    .wrapping_add(1442695040888963407);
                (state >> 33) as usize % bound
            };
            for _ in 0..300 {
                let depth = 129 + next(8000);
                let mut source = String::from("x:=");
                let mut closers = String::new();
                for _ in 0..depth {
                    let (open, close) = EXPRESSION[next(EXPRESSION.len())];
                    source.push_str(open);
                    closers.insert_str(0, close);
                }
                source.push('0');
                source.push_str(&closers);
                let errors = zak_check(&source).unwrap_err();
                assert!(pre_parse_rejection(&errors), "depth {depth}: {source:.80}");
            }
            for _ in 0..100 {
                // Elif chains whose blocks hold ternary fragments.
                let depth = 129 + next(8000);
                let mut source = String::from("x:=1;?x{x=1}");
                for _ in 1..depth {
                    let (open, close) = EXPRESSION[next(EXPRESSION.len())];
                    if next(4) == 0 {
                        source.push_str(&format!(":?x{{x={open}0{close}}}"));
                    } else {
                        source.push_str(":?x{x=1}");
                    }
                }
                let errors = zak_check(&source).unwrap_err();
                assert!(chain_rejection(&errors), "elif depth {depth}");
            }
        })
        .unwrap();
    handle.join().unwrap();
}
