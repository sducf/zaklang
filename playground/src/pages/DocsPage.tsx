import { Link } from "react-router";

const syntax = [
    ["@solve(nums:[I])I{…}", "A function with a typed input and return value"],
    ["total:=0", "Declare a variable; its type is inferred"],
    ["~n:nums{…}", "Loop over each value in an array"],
    ["?n>0{…}:{…}", "An if / else branch"],
    ["^total", "Return a value"],
    ["I · R · B · S", "Integer, float, boolean, and string types"],
    ["[I] · {S:I}", "An integer array and a string-to-integer map"],
];

const sections = [
    { id: "idea", label: "The idea" },
    { id: "prototype", label: "This prototype" },
    { id: "syntax", label: "Zak Core v0.1" },
];

const steps = [
    ["Generate", "Load a public task’s example solution."],
    ["Compile", "Check that source matches the demo fixture."],
    ["Transpile", "Show the fixture’s Python translation."],
    ["Run tests", "Show an illustrative outcome and save a local demo run."],
];

const sectionHead = "scroll-mt-20 border-t border-border-default pt-8";

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
                    <div>
                        <Link className="btn btn-secondary" to="/playground">
                            Try it out
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
                        Prompt overhead counts, too. Fewer completion tokens do
                        not guarantee a cheaper correct solution.
                    </p>
                </section>

                <section
                    id="prototype"
                    className={`${sectionHead} mt-10 flex flex-col gap-4 text-base leading-7`}
                >
                    <span className="label">This prototype</span>
                    <h2 className="text-xl font-semibold tracking-tight">
                        Explore the shape of the pipeline.
                    </h2>
                    <ol className="flex flex-col">
                        {steps.map(([name, text], i) => (
                            <li
                                key={name}
                                className="grid grid-cols-[24px_120px_minmax(0,1fr)] gap-3 border-b border-border-default py-3 max-md:grid-cols-[24px_minmax(0,1fr)]"
                            >
                                <span className="text-text-tertiary">
                                    {i + 1}
                                </span>
                                <strong className="font-semibold">{name}</strong>
                                <span className="text-text-secondary max-md:col-start-2">
                                    {text}
                                </span>
                            </li>
                        ))}
                    </ol>
                    <p className="text-text-secondary">
                        Inference, compilation, sandbox execution, and
                        authentication are not connected. Edited code is
                        preserved but needs a future compiler API to run.
                    </p>
                </section>

                <section
                    id="syntax"
                    className={`${sectionHead} mt-10 flex flex-col gap-4 text-base leading-7`}
                >
                    <div className="flex flex-wrap items-center gap-3">
                        <span className="label">Zak Core v0.1</span>
                        <span className="badge badge-neutral">Draft grammar</span>
                    </div>
                    <h2 className="text-xl font-semibold tracking-tight">
                        A little syntax goes a long way.
                    </h2>
                    <p className="text-text-secondary">
                        Based on the repository’s Lark grammar. Whitespace is
                        ignored; simple statements are separated with
                        semicolons. Function and control-flow blocks use braces.
                        The language is still evolving.
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
