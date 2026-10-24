# Zak Core v0.1

**Spec version:** 0.1  
**Target model:** Llama 3.1 8B Instruct (Q4_K_M GGUF)
**Token count:** PENDING — requires verification using the deployed model's `/tokenize` endpoint
**Compiler validation:** 3/4 reference examples pass the current SD1 compiler subset. The array comprehension example uses valid Zak Core v0.1 syntax but is not yet supported by the SD1 compiler.

## zak_spec

Zak is statically typed; no implicit conversions. Whitespace/newlines are ignored; no comments. Separate simple statements with `;`. Statements ending in `}` need no `;`. Names: `[a-z_][a-z0-9_]*`.

Types: `I` int, `R` float, `B` bool, `S` string, `[T]` array, `{K:V}` map (keys `I` or `S`).
Literals: `12`, `1.5`, `T`, `F`, `"txt"`, `[1,2]`, `{"a":1}`, `[]`, `{}`.

Functions: `@f(a:I,b:S)R{...}` defines a function with required return type; `^e` returns.
Declarations: `x:=e` inferred; `x:[I]=[]` typed (required for empty collections).
Updates: `x=e`, `x+=e`, `x-=e`, `x*=e`, `x/=e`, `x%=e`; `a[i]=e`; `m[k]=e`; `a<<e` appends.

Conditionals: `?c{...}:?d{...}:{...}` if/elif/else.
Loops: `~c{...}` while; `~x:a{...}` array/string/map-key iteration; `~k,v:m{...}` map entries; `~i:0..n{...}` half-open range.
Control: `!` break; `>` continue.

Operators, low to high precedence:
- `c?a:b` ternary
- `|` or; `&` and; `!` not
- `== != < <= > >=` comparisons; `x@a` membership
- `+ -` addition/subtraction (`+` concatenates strings/arrays)
- `* / %` multiplication/division/modulo (`I/I` floors; `I` and `R` do not mix)
- `-x` negation; `#x` length
- `a[i]`, `a[i:j]`, `a[:j]`, `a[i:]` indexing/slicing; `f(x)` calls
- `I(x) R(x) S(x) B(x)` explicit casts

Comprehensions: `[e~x:a]`, `[e~x:a?c]`, `[e~i:0..n]`.

Builtins: `abs min max sum srt rev keys vals pop del spl jn up lo out`.
`srt(a)` sorted copy; `spl(s,d)` split; `jn(a,d)` join; `del(m,k)` remove key; `pop(a)` remove/return last element; `out(x)` print.

Phase 1 keyword/sigil set is frozen for v0.1.

## zak_examples

@fib(n:I)I{?n<2{^n}^fib(n-1)+fib(n-2)}

@cnt(s:S){S:I}{m:{S:I}={};~w:spl(s," "){?w@m{m[w]+=1}:{m[w]=1}}^m}

@ok(o:[{S:I}],lim:I)[B]{^[x["q"]>0&x["p"]<=lim~x:o]}

@bs(a:[I],t:I)I{l:=0;h:=#a-1;~l<=h{m:=(l+h)/2;?a[m]==t{^m}:?a[m]<t{l=m+1}:{h=m-1}}^-1}