import type { ReactNode } from "react";
import { Link } from "react-router";

// Mirrors spec/zak-core-v0.1.md.
const syntax = [
    ["@solve(nums:[I])I{…}", "A function with typed inputs and a return type"],
    ["total:=0", "Declare a variable; its type is inferred"],
    ["seen:[I]=[]", "Declare with a type, required for empty collections"],
    ["x+=1 · a[i]=v · a<<v", "Update a variable, set an index, append to an array"],
    ["?c{…}:?d{…}:{…}", "If, else if, else"],
    ["~c{…}", "Loop while a condition holds"],
    ["~n:nums{…} · ~k,v:m{…}", "Loop over values or keys, or over map entries"],
    ["~i:0..n{…}", "Loop over a half-open range"],
    ["! · >", "Break and continue"],
    ["^total", "Return a value"],
    ["#a · x@a · a[i:j]", "Length, membership, and slicing"],
    ["[x*2~x:a?x>0]", "Build an array from a loop, with an optional filter"],
    ["I · R · B · S", "Integer, float, boolean, and string types"],
    ["[I] · {S:I}", "An integer array and a string-to-integer map"],
    ["I(x) · S(x)", "Explicit casts; nothing converts implicitly"],
];

const sections = [
    { id: "idea", label: "The idea" },
    { id: "playground", label: "Playground" },
    { id: "explorer", label: "Explorer" },
    { id: "compiler", label: "Compiler" },
    { id: "syntax", label: "Zak Core v0.1" },
];

const stages = [
    ["Task", "Pick a task and a language. Zak or Python, same task, same hidden tests."],
    ["Code", "Leave the editor empty and the model writes a solution, or write your own."],
    ["Compile", "Zak compiles to Python. Compile checks your code without running it."],
    ["Run", "The Python runs against hidden tests in an isolated sandbox."],
    ["Results", "Tests passed, attempts, latency, and every token counted."],
];

const explorerViews = [
    ["Run list", "Every run you made, filtered by task, language, or outcome."],
    ["Run detail", "Each attempt: tokens, latency, compile result, tests, and outcome."],
    ["Artifacts", "Open the model's completion and the transpiled Python behind a number."],
    ["Export", "Download the filtered runs and their attempts as CSV."],
];

const sectionHead = "scroll-mt-20 border-t border-border-default pt-8";
const sectionBody = `${sectionHead} mt-10 flex flex-col gap-4 text-base leading-7`;

function Section({
    id,
    label,
    title,
    children,
}: {
    id: string;
    label: string;
    title: string;
    children: ReactNode;
}) {
    return (
        <section id={id} className={sectionBody}>
            <span className="label">{label}</span>
            <h2 className="text-xl font-semibold tracking-tight">{title}</h2>
            {children}
        </section>
    );
}

function Steps({ items, numbered }: { items: string[][]; numbered?: boolean }) {
    const List = numbered ? "ol" : "ul";
    return (
        <List className="flex flex-col">
            {items.map(([name, text], i) => (
                <li
                    key={name}
                    className="grid grid-cols-[24px_120px_minmax(0,1fr)] gap-3 border-b border-border-default py-3 max-md:grid-cols-[24px_minmax(0,1fr)]"
                >
                    <span className="text-text-tertiary">
                        {numbered ? i + 1 : "·"}
                    </span>
                    <strong className="font-semibold">{name}</strong>
                    <span className="text-text-secondary max-md:col-start-2">
                        {text}
                    </span>
                </li>
            ))}
        </List>
    );
}

export default function DocsPage() {
    return (
        <div className="grid grid-cols-[minmax(0,1fr)_200px] gap-16 max-lg:grid-cols-1">
            <article className="max-w-[70ch]">
                <header className="mb-10 flex flex-col gap-4">
                    <span className="label">Small language. Clear intent.</span>
                    <h1 className="text-display font-semibold tracking-tight max-md:text-title">
                        Meet Zak
                    </h1>
                    <p className="text-base text-text-secondary">
                        A deterministic language designed for LLM code
                        generation.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Link className="btn btn-secondary" to="/playground">
                            Try it out
                        </Link>
                        <Link className="btn btn-ghost" to="/explorer">
                            See your runs
                        </Link>
                    </div>
                </header>

                <section
                    id="idea"
                    className={`${sectionHead} flex flex-col gap-4 text-base leading-7`}
                >
                    <span className="label">The idea</span>
                    <h2 className="text-xl font-semibold tracking-tight">
                        Spend tokens on the solution.
                    </h2>
                    <p className="text-text-secondary">
                        Zak uses compact, typed syntax that a compiler can
                        translate to Python. ZakBench compares Zak and Python on
                        the same task, model, seed, and tests.
                    </p>
                    <p className="text-text-secondary">
                        The research question is whether Zak can reduce{" "}
                        <strong className="font-semibold text-text-primary">
                            tokens-to-correctness
                        </strong>
                        : every prompt and completion token, across every
                        attempt, until the program passes.
                    </p>
                    <p className="border-l-2 border-border-action pl-4">
                        Prompt overhead counts, too. The Zak prompt carries the
                        language spec, so fewer completion tokens do not
                        guarantee a cheaper correct solution.
                    </p>
                </section>

                <Section
                    id="playground"
                    label="Playground"
                    title="One task, from prompt to passing tests."
                >
                    <Steps items={stages} numbered />
                    <p className="text-text-secondary">
                        A generated run gets up to three attempts. When the code
                        does not compile or fails a test, a short summary of the
                        error goes back to the model for another try, and those
                        repair tokens count toward the total. Code you write
                        yourself runs once, with no repairs.
                    </p>
                    <p className="text-text-secondary">
                        Token counts come from the model&apos;s own tokenizer,
                        never estimates. Every run uses Llama 3.1 8B Instruct
                        for now. Editing the code clears the last result; the
                        run itself stays in your history.
                    </p>
                    <p className="text-text-secondary">
                        Hidden tests never reach the browser. You see how many
                        passed, not what they check.
                    </p>
                </Section>

                <Section
                    id="explorer"
                    label="Explorer"
                    title="Every run, every attempt, every token."
                >
                    <Steps items={explorerViews} />
                    <p className="text-text-secondary">
                        Unfinished runs refresh on their own until they pass or
                        fail. Hidden tests stay hidden here too.
                    </p>
                </Section>

                <Section
                    id="compiler"
                    label="Compiler"
                    title="zakc, written in Rust."
                >
                    <p className="text-text-secondary">
                        Zak compiles with zakc, a Rust compiler that replaced the
                        original Python and Lark one. It parses the program,
                        checks names, types, and function arguments, then emits
                        Python. The same Zak always produces the same Python.
                    </p>
                    <p className="text-text-secondary">
                        Errors carry a line, a column, a code, and a short
                        message. They are written for the model, since they are
                        what it reads during a repair. The Playground shows them
                        as returned, with a caret under the column.
                    </p>
                </Section>

                <section id="syntax" className={sectionBody}>
                    <div className="flex flex-wrap items-center gap-3">
                        <span className="label">Zak Core v0.1</span>
                        <span className="badge badge-neutral">Draft spec</span>
                    </div>
                    <h2 className="text-xl font-semibold tracking-tight">
                        A little syntax goes a long way.
                    </h2>
                    <p className="text-text-secondary">
                        From the Zak Core v0.1 spec. Whitespace is ignored and
                        there are no comments. Simple statements are separated
                        with semicolons; blocks use braces. The language is
                        still evolving.
                    </p>
                    <div className="overflow-x-auto rounded-md border border-border-default text-sm leading-5">
                        <table className="w-full border-collapse">
                            <thead className="border-b border-border-default bg-surface-default">
                                <tr>
                                    <th className="label h-10 px-4 text-left">
                                        Zak
                                    </th>
                                    <th className="label h-10 px-4 text-left">
                                        Meaning
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {syntax.map(([code, meaning]) => (
                                    <tr
                                        key={code}
                                        className="border-b border-border-default last:border-b-0"
                                    >
                                        <td className="h-12 px-4 whitespace-nowrap">
                                            <code className="text-code-text">
                                                {code}
                                            </code>
                                        </td>
                                        <td className="h-12 px-4 text-text-secondary">
                                            {meaning}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <p className="text-text-secondary">
                        Builtins:{" "}
                        <code className="text-code-text">
                            abs min max sum srt rev keys vals pop del spl jn up
                            lo out
                        </code>
                        .
                    </p>
                </section>
            </article>

            <nav
                aria-label="On this page"
                className="sticky top-24 self-start max-lg:hidden"
            >
                <span className="label">On this page</span>
                <ul className="mt-3 flex flex-col">
                    {sections.map((section) => (
                        <li key={section.id}>
                            <a
                                href={`#${section.id}`}
                                className="flex h-11 items-center text-text-secondary no-underline hover:text-text-primary"
                            >
                                {section.label}
                            </a>
                        </li>
                    ))}
                </ul>
            </nav>
        </div>
    );
}
