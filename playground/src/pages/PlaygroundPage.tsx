import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import ArtifactDialog from "@/components/ArtifactDialog";
import CodeEditor from "@/components/CodeEditor";
import Icon from "@/components/Icon";
import { ApiError } from "@/lib/api";
import {
    compileZak,
    createRun,
    defaultModel,
    signature,
    terminalStatuses,
    useRun,
    useRuns,
    useTask,
    useTasks,
} from "@/lib/benchmark";
import type {
    Attempt,
    CompileResponse,
    CompilerError,
    Language,
    Task,
} from "@/lib/benchmark";

const steps = ["Generate", "Compile", "Transpile", "Run tests"];

/** API errors are shown as returned, prefixed with the HTTP status. */
function errorText(error: unknown) {
    if (error instanceof ApiError) return `HTTP ${error.status}: ${error.message}`;
    return error instanceof Error ? error.message : String(error);
}

function compilerErrorText(error: CompilerError) {
    return `${error.line}:${error.col}: ${error.code}: ${error.message}`;
}

/** Visual state of one pipeline step for the latest attempt. */
function stepState(
    index: number,
    language: Language,
    attempt: Attempt | undefined,
    active: boolean,
) {
    if (language === "python" && (index === 1 || index === 2)) return "skipped";
    const done = [
        attempt !== undefined,
        attempt?.compile_ok === true || language === "python",
        attempt?.transpiled_python != null || language === "python",
        attempt?.tests_total != null,
    ];
    if (index === 1 && attempt?.compile_ok === false) return "failed";
    if (
        index === 3 &&
        attempt?.exec_outcome != null &&
        attempt.exec_outcome !== "pass"
    )
        return "failed";
    if (done[index]) return "done";
    return active && done.slice(0, index).every(Boolean) ? "running" : "";
}

function PlaygroundSession({
    task,
    language,
    titles,
}: {
    task: Task;
    language: Language;
    titles: Map<string, string>;
}) {
    const queryClient = useQueryClient();
    const isZak = language === "zak";
    // null means "not edited": the editor shows the model's latest output.
    const [edited, setEdited] = useState<string | null>(null);
    const [runId, setRunId] = useState<number | null>(null);
    const [compiled, setCompiled] = useState<CompileResponse | null>(null);
    const [outputTab, setOutputTab] = useState("console");
    const [artifact, setArtifact] = useState(false);

    const runQuery = useRun(runId);
    const run = runQuery.data;
    const attempt = run?.attempts.at(-1);
    const finished = run !== undefined && terminalStatuses.has(run.status);
    const polling = runId !== null && !finished && !runQuery.error;

    const compileMutation = useMutation({
        mutationFn: compileZak,
        onSuccess: setCompiled,
    });
    const runMutation = useMutation({
        mutationFn: createRun,
        onSuccess: (created) => {
            queryClient.setQueryData(["run", created.id], created);
            setRunId(created.id);
        },
    });

    const busy = polling || runMutation.isPending || compileMutation.isPending;
    const source = edited ?? attempt?.completion_text ?? "";
    const custom = edited !== null && edited.trim() !== "";
    const python = compiled ? compiled.python : attempt?.transpiled_python;
    const compileErrors = compiled ? compiled.errors : attempt?.compile_errors;
    const requestError =
        runMutation.error ?? compileMutation.error ?? runQuery.error;

    function edit(value: string) {
        setEdited(value);
        setCompiled(null);
    }

    function reset() {
        setEdited(null);
        setRunId(null);
        setCompiled(null);
        runMutation.reset();
        compileMutation.reset();
    }

    function compile() {
        if (busy || !source.trim()) return;
        runMutation.reset();
        compileMutation.mutate(source);
    }

    function startRun() {
        if (busy) return;
        setCompiled(null);
        compileMutation.reset();
        // Without source the model generates a solution (PRD F8).
        runMutation.mutate({
            task_id: task.id,
            language,
            ...(custom ? { source: edited } : {}),
        });
    }

    const stageName = runMutation.isPending
        ? "Starting run…"
        : compileMutation.isPending
          ? "Compiling…"
          : run
            ? `Run #${run.id} · ${run.status}${finished ? "" : "…"}`
            : "Ready when you are";

    return (
        <div
            className="playground-session"
            onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    startRun();
                }
            }}
        >
            <section className="task-card" aria-labelledby="task-title">
                <div className="task-heading">
                    <span className="eyebrow">THE TASK</span>
                    <span className="task-category">{task.category}</span>
                </div>
                <div className="task-description">
                    <div>
                        <h2 id="task-title">{task.title}</h2>
                        <p>{task.prompt}</p>
                        <code className="function-signature">
                            {signature(task)}
                        </code>
                    </div>
                    <div className="public-examples">
                        <span className="eyebrow">INPUTS</span>
                        {task.inputs.map((input) => (
                            <div className="example" key={input.name}>
                                <code>{input.name}</code>
                                <Icon name="arrow" size={14} />
                                <code>{input.type}</code>
                            </div>
                        ))}
                        <div className="example">
                            <code>returns</code>
                            <Icon name="arrow" size={14} />
                            <code>{task.output_type}</code>
                        </div>
                    </div>
                </div>
            </section>
            <div className="editor-section-heading">
                <div>
                    <h2>Your workspace</h2>
                    <span>
                        Leave the editor empty to let the model generate, or
                        write {isZak ? "Zak" : "Python"} yourself.
                    </span>
                </div>
                <button
                    className="text-button"
                    onClick={reset}
                    disabled={busy}
                >
                    <Icon name="reset" size={14} />
                    Reset
                </button>
            </div>
            <section className="editor-workspace" aria-label="Code workspace">
                <div className="editor-topline">
                    <span>
                        <span className="status-dot" />
                        {isZak ? "Zak → Python" : "Python baseline"}
                    </span>
                </div>
                <div className="editor-grid">
                    <CodeEditor
                        value={source}
                        onChange={edit}
                        language={language}
                        label={isZak ? "solution.zak" : "solution.py"}
                        disabled={busy}
                    />
                    <div className="output-editor">
                        <CodeEditor
                            value={isZak ? (python ?? "") : ""}
                            language="python"
                            readOnly
                            label="transpiled.py"
                        />
                        <span
                            className={`preview-tag ${python ? "completed" : ""}`}
                        >
                            {!isZak
                                ? "Python runs as written"
                                : python
                                  ? "Transpiled"
                                  : "Not compiled yet"}
                        </span>
                    </div>
                </div>
                <div className="pipeline-toolbar">
                    <div
                        className="pipeline-steps"
                        aria-label="Pipeline stages"
                    >
                        {steps.map((step, i) => {
                            const state = stepState(
                                i,
                                language,
                                attempt,
                                polling,
                            );
                            return (
                                <span
                                    key={step}
                                    className={`step-button ${state}`}
                                >
                                    <span className="step-number">
                                        {state === "done" ? (
                                            <Icon name="check" size={11} />
                                        ) : state === "failed" ? (
                                            <Icon name="close" size={11} />
                                        ) : (
                                            i + 1
                                        )}
                                    </span>
                                    {state === "skipped"
                                        ? `${step} · skip`
                                        : step}
                                    {i < 3 && (
                                        <Icon
                                            name="chevron"
                                            size={11}
                                            style={{
                                                transform: "rotate(-90deg)",
                                            }}
                                        />
                                    )}
                                </span>
                            );
                        })}
                    </div>
                    <div className="pipeline-actions">
                        {isZak && (
                            <button
                                className="button secondary"
                                onClick={compile}
                                disabled={busy || !source.trim()}
                            >
                                <Icon name="code" size={14} />
                                Compile
                            </button>
                        )}
                        <button
                            className="button primary"
                            onClick={startRun}
                            disabled={busy}
                        >
                            <Icon name="play" size={14} />
                            {busy && !compileMutation.isPending
                                ? "Running…"
                                : custom
                                  ? "Run my code"
                                  : "Generate & run"}
                            <kbd>⌘ ↵</kbd>
                        </button>
                    </div>
                </div>
            </section>
            <section className="results-panel" aria-label="Run output">
                <div className="results-header">
                    <div
                        className="result-tabs"
                        role="tablist"
                        aria-label="Output tabs"
                    >
                        {["console", "results", "history"].map((tab) => (
                            <button
                                role="tab"
                                aria-selected={outputTab === tab}
                                aria-controls="output-tabpanel"
                                id={`tab-${tab}`}
                                key={tab}
                                onClick={() => setOutputTab(tab)}
                                className={outputTab === tab ? "selected" : ""}
                            >
                                {tab === "console" && (
                                    <Icon name="terminal" size={14} />
                                )}
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                            </button>
                        ))}
                    </div>
                    <span
                        className={`run-state ${run?.status === "passed" ? "success" : ""}`}
                        aria-live="polite"
                    >
                        <span className="status-dot" />
                        {stageName}
                    </span>
                </div>
                <div
                    className="results-body"
                    id="output-tabpanel"
                    role="tabpanel"
                    aria-labelledby={`tab-${outputTab}`}
                    aria-live="polite"
                >
                    {requestError && (
                        <p className="compiler-error" role="alert">
                            {errorText(requestError)}
                        </p>
                    )}
                    {compileErrors?.map((error, i) => (
                        <p className="compiler-error" key={i}>
                            {compilerErrorText(error)}
                        </p>
                    ))}
                    {outputTab === "console" && (
                        <div className="console-lines">
                            <div>
                                <span className="console-prefix">›</span>
                                <span>Zak playground connected.</span>
                                <span className="console-comment">
                                    // backend API
                                </span>
                            </div>
                            {compiled && (
                                <div>
                                    <span
                                        className={`console-prefix ${compiled.ok ? "success" : "failure"}`}
                                    >
                                        {compiled.ok ? "✓" : "✗"}
                                    </span>
                                    {compiled.ok
                                        ? "Compiled. Transpiled Python is on the right."
                                        : `Compile failed with ${compiled.errors.length} error(s).`}
                                </div>
                            )}
                            {run && (
                                <div>
                                    <span className="console-prefix">›</span>
                                    Run #{run.id} {run.status}
                                    {edited === null && (
                                        <span className="console-comment">
                                            model-generated source
                                        </span>
                                    )}
                                </div>
                            )}
                            {run?.attempts.map((item) => (
                                <div key={item.index}>
                                    <span
                                        className={`console-prefix ${item.exec_outcome === "pass" ? "success" : "failure"}`}
                                    >
                                        {item.exec_outcome === "pass"
                                            ? "✓"
                                            : "✗"}
                                    </span>
                                    Attempt {item.index}: compile{" "}
                                    {item.compile_ok === null
                                        ? "skipped"
                                        : item.compile_ok
                                          ? "ok"
                                          : "failed"}
                                    , outcome {item.exec_outcome ?? "none"}
                                    {item.tests_total != null &&
                                        `, tests ${item.tests_passed}/${item.tests_total}`}
                                </div>
                            ))}
                            {!run && !compiled && (
                                <div>
                                    <span className="console-prefix muted">
                                        ·
                                    </span>
                                    <span className="muted">
                                        Select Generate &amp; run, or write
                                        code and run it.
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                    {outputTab === "results" &&
                        (run && finished ? (
                            <div className="run-metrics">
                                <div>
                                    <span className="eyebrow">OUTCOME</span>
                                    <strong
                                        className={
                                            run.status === "passed"
                                                ? "success"
                                                : "failure"
                                        }
                                    >
                                        {run.status}
                                    </strong>
                                    <small>
                                        {attempt?.exec_outcome ?? "no outcome"}
                                    </small>
                                </div>
                                <div>
                                    <span className="eyebrow">TESTS</span>
                                    <strong>
                                        {attempt?.tests_passed ?? "–"}{" "}
                                        <span className="muted">
                                            / {attempt?.tests_total ?? "–"}
                                        </span>
                                    </strong>
                                    <small>Hidden tests, server side</small>
                                </div>
                                <button onClick={() => setArtifact(true)}>
                                    <span className="eyebrow">
                                        TOTAL TOKENS
                                    </span>
                                    <strong>
                                        {run.total_tokens.toLocaleString()}{" "}
                                        <Icon name="external" size={13} />
                                    </strong>
                                    <small>
                                        {run.prompt_tokens_total.toLocaleString()}{" "}
                                        prompt ·{" "}
                                        {run.completion_tokens_total.toLocaleString()}{" "}
                                        completion
                                    </small>
                                </button>
                                <div>
                                    <span className="eyebrow">LATENCY</span>
                                    <strong>
                                        {Math.round(
                                            run.latency_ms_total,
                                        ).toLocaleString()}
                                        <span className="muted">ms</span>
                                    </strong>
                                    <small>
                                        {run.attempts_used} attempt
                                        {run.attempts_used === 1 ? "" : "s"}
                                    </small>
                                </div>
                            </div>
                        ) : (
                            <div className="empty-inline">
                                <Icon name="chart" />
                                <span>
                                    Results appear when a run finishes.
                                </span>
                            </div>
                        ))}
                    {outputTab === "history" && <RunHistory titles={titles} />}
                </div>
                <div className="results-footnote">
                    <Icon name="book" size={13} />
                    <span>
                        Hidden tests are never sent to this browser.
                    </span>
                    <Link to="/docs">
                        How it works <Icon name="arrow" size={12} />
                    </Link>
                </div>
            </section>
            {artifact && run && (
                <ArtifactDialog
                    title={`Token accounting · run #${run.id}`}
                    onClose={() => setArtifact(false)}
                >
                    <p>
                        Token counts come from the model&apos;s own tokenizer
                        and include every attempt, repairs included.
                    </p>
                    <dl className="artifact-facts">
                        <div>
                            <dt>Prompt (including language instructions)</dt>
                            <dd>{run.prompt_tokens_total}</dd>
                        </div>
                        <div>
                            <dt>Completion</dt>
                            <dd>{run.completion_tokens_total}</dd>
                        </div>
                        <div>
                            <dt>
                                Total across {run.attempts_used} attempt
                                {run.attempts_used === 1 ? "" : "s"}
                            </dt>
                            <dd>{run.total_tokens}</dd>
                        </div>
                        {run.attempts.map((item) => (
                            <div key={item.index}>
                                <dt>Attempt {item.index}</dt>
                                <dd>
                                    {item.prompt_tokens ?? "–"} +{" "}
                                    {item.completion_tokens ?? "–"} ·{" "}
                                    {item.latency_ms ?? "–"} ms
                                </dd>
                            </div>
                        ))}
                        <div>
                            <dt>Model / temperature</dt>
                            <dd>
                                {run.model_name} / {run.temperature ?? "–"}
                            </dd>
                        </div>
                    </dl>
                    <pre className="artifact-code">{source}</pre>
                </ArtifactDialog>
            )}
        </div>
    );
}

function RunHistory({ titles }: { titles: Map<string, string> }) {
    const runs = useRuns();
    if (runs.error) {
        return <p className="compiler-error">{errorText(runs.error)}</p>;
    }
    if (!runs.data?.length) {
        return (
            <div className="empty-inline">
                <Icon name="clock" />
                <span>
                    {runs.isPending ? "Loading runs…" : "Your runs show up here."}
                </span>
            </div>
        );
    }
    return (
        <div className="history-list">
            {runs.data.slice(0, 5).map((run) => (
                <div className="history-row" key={run.id}>
                    <span
                        className={
                            run.status === "passed" ? "success" : "failure"
                        }
                    >
                        <Icon
                            name={run.status === "passed" ? "check" : "close"}
                            size={14}
                        />
                    </span>
                    <span>{titles.get(run.task_id) ?? run.task_id}</span>
                    <code>{run.language}</code>
                    <span>
                        #{run.id} · {run.status}
                    </span>
                </div>
            ))}
        </div>
    );
}

export default function PlaygroundPage() {
    const [params, setParams] = useSearchParams();
    const tasks = useTasks();
    const taskId = params.get("task") ?? tasks.data?.[0]?.id;
    const task = useTask(taskId);
    const language: Language =
        params.get("lang") === "python" ? "python" : "zak";
    const titles = new Map(
        (tasks.data ?? []).map((item) => [item.id, item.title]),
    );

    function select(nextTaskId: string, lang: Language) {
        setParams({ task: nextTaskId, lang });
    }

    const loadError = tasks.error ?? task.error;

    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        THE ZAKLANG LAB
                    </div>
                    <h1>
                        Playground<span className="title-dot">.</span>
                    </h1>
                    <p>
                        From a little Zak to working Python. Explore the
                        pipeline.
                    </p>
                </div>
                <Link to="/explorer" className="button secondary">
                    Open Explorer <Icon name="arrow" size={15} />
                </Link>
            </div>
            <div className="configuration-row">
                <label className="select-field">
                    <span className="eyebrow">01 / TASK</span>
                    <span className="select-wrapper">
                        <Icon name="code" size={16} />
                        <select
                            aria-label="Task"
                            value={taskId ?? ""}
                            disabled={!tasks.data}
                            onChange={(event) =>
                                select(event.target.value, language)
                            }
                        >
                            {tasks.data?.map((item) => (
                                <option key={item.id} value={item.id}>
                                    {item.title}
                                </option>
                            ))}
                        </select>
                        <Icon name="chevron" size={14} />
                    </span>
                </label>
                <label className="select-field model-field">
                    <span className="eyebrow">02 / MODEL</span>
                    <span className="select-wrapper">
                        <Icon name="cpu" size={16} />
                        <select aria-label="Model" defaultValue="default">
                            <option value="default">{defaultModel}</option>
                        </select>
                        <span className="quant-badge">Q4_K_M</span>
                        <Icon name="chevron" size={14} />
                    </span>
                </label>
                <div className="language-field">
                    <span className="eyebrow">03 / LANGUAGE</span>
                    <div className="segmented-control" aria-label="Language">
                        {(["zak", "python"] as const).map((lang) => (
                            <button
                                key={lang}
                                aria-pressed={language === lang}
                                className={language === lang ? "selected" : ""}
                                disabled={!taskId}
                                onClick={() => taskId && select(taskId, lang)}
                            >
                                {lang === "zak" ? (
                                    <>
                                        <span className="mini-z">z</span>Zak
                                    </>
                                ) : (
                                    "Python"
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            {loadError ? (
                <p className="compiler-error" role="alert">
                    {errorText(loadError)}
                </p>
            ) : task.data ? (
                <PlaygroundSession
                    key={`${task.data.id}-${language}`}
                    task={task.data}
                    language={language}
                    titles={titles}
                />
            ) : (
                <div className="empty-inline">
                    <Icon name="clock" />
                    <span>Loading tasks…</span>
                </div>
            )}
        </>
    );
}
