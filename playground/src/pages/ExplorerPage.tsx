import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import ArtifactDialog from "@/components/ArtifactDialog";
import CodeEditor from "@/components/CodeEditor";
import Icon from "@/components/Icon";
import { sampleRuns, tasks } from "@/lib/demo";
import type { DemoRun } from "@/lib/demo";
import { useDemoRuns } from "@/lib/run-store";

export default function ExplorerPage() {
    const localRuns = useDemoRuns();
    const [params, setParams] = useSearchParams();
    const [taskId, setTaskId] = useState(tasks[0].id);
    const [language, setLanguage] = useState("all");
    const [dataset, setDataset] = useState("sample");
    const [detail, setDetail] = useState<DemoRun | null>(null);
    const task = tasks.find((item) => item.id === taskId)!;
    const zak = sampleRuns.find(
        (run) => run.taskId === taskId && run.language === "zak",
    )!;
    const python = sampleRuns.find(
        (run) => run.taskId === taskId && run.language === "python",
    )!;
    const zakTotal = zak.promptTokens + zak.completionTokens;
    const pythonTotal = python.promptTokens + python.completionTokens;
    const selectedRun =
        [...localRuns, ...sampleRuns].find(
            (run) => run.id === params.get("run"),
        ) ?? detail;
    const displayedRuns = (
        dataset === "sample" ? sampleRuns : localRuns
    ).filter((run) => language === "all" || run.language === language);

    function exportCsv() {
        const rows = [
            [
                "id",
                "task",
                "language",
                "model",
                "seed",
                "outcome",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "created_at",
                "data_source",
            ],
            ...displayedRuns.map((run) => [
                run.id,
                run.taskId,
                run.language,
                run.model,
                String(run.seed),
                run.passed ? "demo_passed" : "demo_failed",
                String(run.promptTokens),
                String(run.completionTokens),
                String(run.promptTokens + run.completionTokens),
                run.createdAt,
                "demo_fixture",
            ]),
        ];
        const csv = rows
            .map((row) =>
                row.map((cell) => `"${cell.replaceAll('"', '""')}"`).join(","),
            )
            .join("\r\n");
        const url = URL.createObjectURL(
            new Blob([csv], { type: "text/csv;charset=utf-8;" }),
        );
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = "zakbench-demo-runs.csv";
        anchor.click();
        URL.revokeObjectURL(url);
    }

    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        MEASURE WHAT MATTERS
                    </div>
                    <h1>
                        Explorer<span className="title-dot">.</span>
                    </h1>
                    <p>
                        Same task. Same model. Two languages. See the whole
                        cost.
                    </p>
                </div>
                <Link
                    className="button primary"
                    to={`/playground?task=${taskId}`}
                >
                    <Icon name="plus" size={15} />
                    New playground run
                </Link>
            </div>
            <div className="notice">
                <Icon name="chart" size={17} />
                <span>
                    <strong>Sample benchmark data.</strong> All outcomes and
                    token counts below are illustrative. They are not research
                    results.
                </span>
                <span className="small-badge">DEMO</span>
            </div>
            <div className="section-heading">
                <div>
                    <h2>Paired comparison</h2>
                    <p>Including the cost of teaching the model Zak.</p>
                </div>
                <label className="compact-select">
                    <select
                        aria-label="Comparison task"
                        value={taskId}
                        onChange={(event) => setTaskId(event.target.value)}
                    >
                        {tasks.map((item) => (
                            <option value={item.id} key={item.id}>
                                {item.title}
                            </option>
                        ))}
                    </select>
                    <Icon name="chevron" size={14} />
                </label>
            </div>
            <div className="comparison-grid">
                {[zak, python].map((run) => (
                    <section
                        className={`comparison-card ${run.language}`}
                        key={run.language}
                    >
                        <div className="comparison-top">
                            <span className="comparison-language">
                                {run.language === "zak" ? (
                                    <span className="mini-z">z</span>
                                ) : (
                                    <Icon name="code" />
                                )}{" "}
                                {run.language === "zak" ? "Zak" : "Python"}
                            </span>
                            <span className="outcome-pill">
                                <Icon name="check" size={12} />
                                Demo passed
                            </span>
                        </div>
                        <button
                            className="token-total"
                            onClick={() => setDetail(run)}
                        >
                            {(
                                run.promptTokens + run.completionTokens
                            ).toLocaleString()}
                            <span>
                                total tokens <Icon name="external" size={12} />
                            </span>
                        </button>
                        <div className="token-bar">
                            <span
                                style={{
                                    width: `${(run.promptTokens / (run.promptTokens + run.completionTokens)) * 100}%`,
                                }}
                            />
                            <span />
                        </div>
                        <div className="token-breakdown">
                            <button onClick={() => setDetail(run)}>
                                <span className="legend-square" />
                                Prompt{" "}
                                <strong>
                                    {run.promptTokens.toLocaleString()}
                                </strong>
                            </button>
                            <button onClick={() => setDetail(run)}>
                                <span className="legend-square completion" />
                                Completion{" "}
                                <strong>{run.completionTokens}</strong>
                            </button>
                        </div>
                        <div className="comparison-meta">
                            <span>Seed 42 · Temperature 0</span>
                            <span>1 attempt</span>
                        </div>
                    </section>
                ))}
            </div>
            <div className="comparison-insight">
                <span className="ratio">
                    {(zakTotal / pythonTotal).toFixed(2)}
                    <small>×</small>
                </span>
                <div>
                    <strong>Zak / Python total-token ratio</strong>
                    <p>
                        In this fixture, shorter output does not offset Zak’s
                        prompt overhead. Completion tokens alone tell only part
                        of the story.
                    </p>
                </div>
                <span className="insight-task">{task.title}</span>
            </div>
            <div className="section-heading table-heading">
                <div>
                    <h2>Run history</h2>
                    <p>Inspect the source and accounting behind each run.</p>
                </div>
                <button
                    className="button secondary"
                    onClick={exportCsv}
                    disabled={!displayedRuns.length}
                >
                    <Icon name="download" size={15} />
                    Export CSV
                </button>
            </div>
            <div className="run-table-panel">
                <div className="table-filters">
                    <div className="segmented-control">
                        <button
                            className={dataset === "sample" ? "selected" : ""}
                            aria-pressed={dataset === "sample"}
                            onClick={() => setDataset("sample")}
                        >
                            Sample runs
                        </button>
                        <button
                            className={dataset === "local" ? "selected" : ""}
                            aria-pressed={dataset === "local"}
                            onClick={() => setDataset("local")}
                        >
                            My demo runs{" "}
                            <span className="count-badge">
                                {localRuns.length}
                            </span>
                        </button>
                    </div>
                    <label className="compact-select">
                        <select
                            aria-label="Filter run language"
                            value={language}
                            onChange={(event) =>
                                setLanguage(event.target.value)
                            }
                        >
                            <option value="all">All languages</option>
                            <option value="zak">Zak</option>
                            <option value="python">Python</option>
                        </select>
                        <Icon name="chevron" size={13} />
                    </label>
                </div>
                <div className="table-scroll">
                    <table>
                        <thead>
                            <tr>
                                <th>Task</th>
                                <th>Language</th>
                                <th>Outcome</th>
                                <th>Prompt</th>
                                <th>Completion</th>
                                <th>Total tokens</th>
                                <th>Seed</th>
                                <th>
                                    <span className="sr-only">Details</span>
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {displayedRuns.map((run) => (
                                <tr key={run.id}>
                                    <td>
                                        <button
                                            className="table-task"
                                            onClick={() => setDetail(run)}
                                        >
                                            {tasks.find(
                                                (item) =>
                                                    item.id === run.taskId,
                                            )?.title ?? run.taskId}
                                            <small>{run.id.slice(0, 19)}</small>
                                        </button>
                                    </td>
                                    <td>
                                        <span
                                            className={`language-pill ${run.language}`}
                                        >
                                            {run.language === "zak"
                                                ? "Zak"
                                                : "Python"}
                                        </span>
                                    </td>
                                    <td>
                                        <span
                                            className={
                                                run.passed
                                                    ? "success"
                                                    : "compiler-error"
                                            }
                                        >
                                            {run.passed
                                                ? "Demo passed"
                                                : "Demo failed"}
                                        </span>
                                    </td>
                                    <td>
                                        <button
                                            className="number-link"
                                            onClick={() => setDetail(run)}
                                        >
                                            {run.promptTokens.toLocaleString()}
                                        </button>
                                    </td>
                                    <td>
                                        <button
                                            className="number-link"
                                            onClick={() => setDetail(run)}
                                        >
                                            {run.completionTokens}
                                        </button>
                                    </td>
                                    <td>
                                        <button
                                            className="number-link total"
                                            onClick={() => setDetail(run)}
                                        >
                                            {(
                                                run.promptTokens +
                                                run.completionTokens
                                            ).toLocaleString()}
                                        </button>
                                    </td>
                                    <td className="mono muted">{run.seed}</td>
                                    <td>
                                        <button
                                            className="icon-button"
                                            aria-label={`Inspect ${run.taskId} ${run.language} run`}
                                            onClick={() => setDetail(run)}
                                        >
                                            <Icon name="arrow" size={15} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {!displayedRuns.length && (
                    <div className="table-empty">
                        <Icon name="clock" size={24} />
                        <h3>No demo runs yet</h3>
                        <p>
                            Run a task in the Playground to start your local
                            history.
                        </p>
                        <Link to="/playground" className="button secondary">
                            Open Playground <Icon name="arrow" size={14} />
                        </Link>
                    </div>
                )}
                <div className="table-footer">
                    {displayedRuns.length} runs
                    <span>
                        {dataset === "sample"
                            ? "Illustrative fixtures"
                            : "Stored in this browser"}{" "}
                        · Llama 3.1 8B Instruct
                    </span>
                </div>
            </div>
            {selectedRun && (
                <ArtifactDialog
                    title={`${tasks.find((item) => item.id === selectedRun.taskId)?.title ?? selectedRun.taskId} · ${selectedRun.language}`}
                    onClose={() => {
                        setDetail(null);
                        setParams({});
                    }}
                >
                    <p>
                        Demo artifact. Counts are illustrative; no inference,
                        compilation, or sandbox execution was performed.
                    </p>
                    <dl className="artifact-facts">
                        <div>
                            <dt>
                                Prompt tokens (includes language instructions)
                            </dt>
                            <dd>{selectedRun.promptTokens}</dd>
                        </div>
                        <div>
                            <dt>Completion tokens</dt>
                            <dd>{selectedRun.completionTokens}</dd>
                        </div>
                        <div>
                            <dt>Total tokens</dt>
                            <dd>
                                {selectedRun.promptTokens +
                                    selectedRun.completionTokens}
                            </dd>
                        </div>
                        <div>
                            <dt>Model</dt>
                            <dd>{selectedRun.model}</dd>
                        </div>
                        <div>
                            <dt>Seed / temperature / attempts</dt>
                            <dd>{selectedRun.seed} / 0.0 / 1</dd>
                        </div>
                    </dl>
                    <CodeEditor
                        value={selectedRun.source}
                        language={selectedRun.language}
                        readOnly
                        label={`solution.${selectedRun.language === "zak" ? "zak" : "py"}`}
                    />
                    <Link
                        className="button secondary dialog-link"
                        to={`/playground?task=${selectedRun.taskId}&lang=${selectedRun.language}`}
                    >
                        Open task in Playground <Icon name="arrow" size={14} />
                    </Link>
                </ArtifactDialog>
            )}
        </>
    );
}
