import { Link } from "react-router";
import Icon from "@/components/Icon";

const syntax = [
    ["@solve(nums:[I])I{…}", "A function with a typed input and return value"],
    ["total:=0", "Declare a variable; its type is inferred"],
    ["~n:nums{…}", "Loop over each value in an array"],
    ["?n>0{…}:{…}", "An if / else branch"],
    ["^total", "Return a value"],
    ["I · R · B · S", "Integer, float, boolean, and string types"],
    ["[I] · {S:I}", "An integer array and a string-to-integer map"],
];

export default function DocsPage() {
    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        SMALL LANGUAGE. CLEAR INTENT.
                    </div>
                    <h1>
                        Meet Zak<span className="title-dot">.</span>
                    </h1>
                    <p>
                        A deterministic language designed for LLM code
                        generation.
                    </p>
                </div>
                <Link className="button secondary" to="/playground">
                    Try it out <Icon name="arrow" size={15} />
                </Link>
            </div>
            <div className="docs-grid">
                <section className="docs-card">
                    <span className="eyebrow">THE IDEA</span>
                    <h2>Spend tokens on the solution.</h2>
                    <p>
                        Zak uses compact, typed syntax that a compiler can
                        translate to Python. ZakBench compares Zak and Python on
                        the same task, model, seed, and tests.
                    </p>
                    <p>
                        The research question is whether Zak can reduce{" "}
                        <strong>tokens-to-correctness</strong>: every prompt and
                        completion token, across every attempt, until the
                        program passes.
                    </p>
                    <div className="docs-callout">
                        Prompt overhead counts, too. Fewer completion tokens do
                        not guarantee a cheaper correct solution.
                    </div>
                </section>
                <section className="docs-card">
                    <span className="eyebrow">THIS PROTOTYPE</span>
                    <h2>Explore the shape of the pipeline.</h2>
                    <ol className="docs-steps">
                        <li>
                            <strong>Generate</strong>
                            <span>Load a public task’s example solution.</span>
                        </li>
                        <li>
                            <strong>Compile</strong>
                            <span>
                                Check that source matches the demo fixture.
                            </span>
                        </li>
                        <li>
                            <strong>Transpile</strong>
                            <span>Show the fixture’s Python translation.</span>
                        </li>
                        <li>
                            <strong>Run tests</strong>
                            <span>
                                Show an illustrative outcome and save a local
                                demo run.
                            </span>
                        </li>
                    </ol>
                    <p className="muted">
                        Inference, compilation, sandbox execution, and
                        authentication are not connected. Edited code is
                        preserved but needs a future compiler API to run.
                    </p>
                </section>
            </div>
            <section className="docs-card syntax-card">
                <div className="section-heading">
                    <div>
                        <span className="eyebrow">ZAK CORE v0.1</span>
                        <h2>A little syntax goes a long way.</h2>
                    </div>
                    <span className="small-badge">DRAFT GRAMMAR</span>
                </div>
                <p>
                    Based on the repository’s Lark grammar. Whitespace is
                    ignored; simple statements are separated with semicolons.
                    Function and control-flow blocks use braces. The language is
                    still evolving.
                </p>
                <div className="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Zak</th>
                                <th>Meaning</th>
                            </tr>
                        </thead>
                        <tbody>
                            {syntax.map(([code, meaning]) => (
                                <tr key={code}>
                                    <td>
                                        <code className="syntax-example">
                                            {code}
                                        </code>
                                    </td>
                                    <td>{meaning}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </section>
        </>
    );
}
