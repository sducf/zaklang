import { useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import ArtifactDialog from "@/components/ArtifactDialog";
import CodeEditor from "@/components/CodeEditor";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import AttemptTable from "@/components/playground/AttemptTable";
import RecentRuns from "@/components/playground/RecentRuns";
import Stage from "@/components/playground/Stage";
import type { StageState } from "@/components/playground/Stage";
import { ApiError } from "@/lib/api";
import {
    compileZak,
    createRun,
    defaultModel,
    signature,
    terminalStatuses,
    useRun,
    useTask,
    useTasks,
} from "@/lib/benchmark";
import type {
    Attempt,
    CompileResponse,
    CompilerError,
    Language,
    Run,
    Task,
} from "@/lib/benchmark";

/** API errors are shown as returned, prefixed with the HTTP status. */
function errorText(error: unknown) {
    if (error instanceof ApiError) return `HTTP ${error.status}: ${error.message}`;
    return error instanceof Error ? error.message : String(error);
}

const outcomeLabels = {
    pass: "Passed",
    fail: "Failed",
    timeout: "Timeout",
    oom: "Out of memory",
    crash: "Crashed",
    not_run: "Not run",
};

function plural(count: number, word: string) {
    return `${count} ${word}${count === 1 ? "" : "s"}`;
}

function PageHead({ children }: { children?: ReactNode }) {
    return (
        <div className="mb-8 flex items-end justify-between gap-6 max-md:mb-6 max-md:flex-col max-md:items-stretch">
            <div>
                <h1 className="text-display font-semibold tracking-tight max-md:text-title">
                    Playground
                </h1>
                <p className="mt-2 max-w-[60ch] text-base text-text-secondary">
                    From a little Zak to working Python. Explore the pipeline.
                </p>
            </div>
            {children}
        </div>
    );
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
    return (
        <div className="flex flex-col gap-0.5">
            <span className="label">{label}</span>
            <span className="font-medium">{children}</span>
        </div>
    );
}

/** Run, status, attempts and the running token total for the current run. */
function RunBar({ run }: { run: Run | undefined }) {
    return (
        <div
            className="flex flex-wrap items-center gap-x-5 gap-y-2 rounded-lg border border-border-default bg-surface-default px-4 py-3"
            aria-label="Current run"
            aria-live="polite"
        >
            <Stat label="Run">{run ? `#${run.id}` : "–"}</Stat>
            <Stat label="Status">
                {run ? (
                    <StatusBadge status={run.status} />
                ) : (
                    <span className="badge badge-outline">Ready</span>
                )}
            </Stat>
            <Stat label="Attempts">{run ? run.attempts_used : "–"}</Stat>
            <div className="flex flex-col gap-0.5">
                <span className="label">Total tokens</span>
                <span className="text-xl font-medium">
                    {run ? run.total_tokens.toLocaleString() : "–"}
                </span>
            </div>
        </div>
    );
}

/** The real compiler error, with the offending line and a caret under the column. */
function CompileErrors({
    errors,
    source,
}: {
    errors: CompilerError[];
    source: string;
}) {
    const lines = source.split("\n");
    return (
        <>
            {errors.map((error, i) => {
                const text = lines[error.line - 1];
                const gutter = String(error.line);
                return (
                    <div
                        key={i}
                        className="overflow-hidden rounded-md border border-border-error bg-surface-page"
                    >
                        <div className="flex items-center gap-2 border-b border-border-default px-4 py-2.5 font-mono font-medium text-text-error">
                            <Icon name="alert" />
                            {error.code} at {error.line}:{error.col}{" "}
                            {error.message}
                        </div>
                        {text !== undefined && (
                            <pre className="m-0 overflow-x-auto px-4 py-3 text-code-text">
                                {`${gutter} | ${text}\n${" ".repeat(gutter.length)} | ${" ".repeat(Math.max(error.col - 1, 0))}`}
                                <span className="text-text-error">^</span>
                            </pre>
                        )}
                    </div>
                );
            })}
        </>
    );
}

/** Tests passed out of total. The hidden tests themselves never reach the browser. */
function TestMeter({ passed, total }: { passed: number; total: number }) {
    return (
        <div
            className="flex gap-1"
            role="img"
            aria-label={`${passed} of ${total} hidden tests passed`}
        >
            {Array.from({ length: total }, (_, i) => (
                <span
                    key={i}
                    className={`h-2 flex-1 animate-rise rounded-full ${
                        i < passed ? "bg-surface-action" : "bg-surface-raised"
                    }`}
                    style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}
                />
            ))}
        </div>
    );
}

function PlaygroundSession({
    task,
    language,
    controls,
}: {
    task: Task;
    language: Language;
    controls: ReactNode;
}) {
    const queryClient = useQueryClient();
    const isZak = language === "zak";
    // null means "not edited": the editor shows the model's latest output.
    const [edited, setEdited] = useState<string | null>(null);
    const [runId, setRunId] = useState<number | null>(null);
    const [compiled, setCompiled] = useState<CompileResponse | null>(null);
    const [artifact, setArtifact] = useState(false);

    const runQuery = useRun(runId);
    const run = runQuery.data;
    const attempt: Attempt | undefined = run?.attempts.at(-1);
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

    // Code
    const codeState: StageState = run || compiled ? "done" : "active";

    // Compile
    let compileState: StageState = "waiting";
    let compileSummary: ReactNode = "Waits for code";
    let compileBody: ReactNode = null;
    if (!isZak) {
        compileState = "skipped";
        compileSummary = "Python runs as written";
    } else if (compileMutation.isPending) {
        compileState = "running";
        compileSummary = "Compiling…";
    } else if (compiled) {
        compileState = compiled.ok ? "done" : "failed";
        compileSummary = compiled.ok
            ? "Zak to Python, no errors"
            : `Did not compile (${plural(compiled.errors.length, "error")})`;
        if (!compiled.ok)
            compileBody = (
                <CompileErrors errors={compiled.errors} source={source} />
            );
    } else if (attempt?.compile_ok === true) {
        compileState = "done";
        compileSummary = "Zak to Python, no errors";
    } else if (attempt?.compile_ok === false) {
        compileState = "failed";
        compileSummary = `Attempt ${attempt.index} did not compile`;
        compileBody = (
            <>
                <CompileErrors
                    errors={attempt.compile_errors}
                    source={attempt.completion_text}
                />
                {polling && (
                    <div className="flex items-center gap-2 text-text-secondary">
                        <Icon name="spinner" className="animate-spin" />
                        Sending the error back to the model for another
                        attempt.
                    </div>
                )}
            </>
        );
    } else if (polling || runMutation.isPending) {
        compileState = "running";
        compileSummary = attempt ? "Compiling…" : "Waiting for the model…";
    }

    // Run
    const outcome = attempt?.exec_outcome;
    const tests =
        attempt?.tests_total != null
            ? `${attempt.tests_passed ?? 0} of ${attempt.tests_total} passed`
            : null;
    const readyToRun = !isZak || attempt?.compile_ok === true;
    let runState: StageState = "waiting";
    let runSummary: ReactNode = isZak ? "Waits for Compile" : "Waits for code";
    if (outcome === "pass") {
        runState = "done";
        runSummary = "Hidden tests in the sandbox";
    } else if (outcome && outcome !== "not_run") {
        runState = "failed";
        runSummary = outcomeLabels[outcome];
    } else if (polling && readyToRun && attempt) {
        runState = "running";
        runSummary = "Running hidden tests in the sandbox";
    } else if (finished && run.status !== "passed" && attempt) {
        runState = "failed";
        runSummary = "Did not run";
    }

    // Results
    const passed = finished && run.status === "passed";

    return (
        <div
            onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    startRun();
                }
            }}
        >
            <PageHead>
                <RunBar run={run} />
            </PageHead>

            {requestError && (
                <p
                    className="mb-4 rounded-md border border-border-error px-4 py-3 text-text-error"
                    role="alert"
                >
                    {errorText(requestError)}
                </p>
            )}

            <div className="flex flex-col">
                <Stage
                    id="stage-task"
                    title="Task"
                    state="done"
                    meta={<span>{task.category}</span>}
                >
                    {controls}
                    <div className="grid grid-cols-[minmax(0,1fr)_260px] gap-6 border-t border-border-default pt-4 max-md:grid-cols-1">
                        <div>
                            <h3 className="mb-1.5 text-xl font-semibold tracking-tight">
                                {task.title}
                            </h3>
                            <p className="mb-3 max-w-[70ch] leading-[22px] text-text-secondary">
                                {task.prompt}
                            </p>
                            <code className="inline-block rounded-sm bg-surface-page px-2 py-1 text-[13px] leading-5 text-code-text">
                                {signature(task)}
                            </code>
                        </div>
                        <div className="flex flex-col gap-2">
                            <span className="label">Inputs</span>
                            {task.inputs.map((input) => (
                                <div
                                    key={input.name}
                                    className="flex justify-between gap-3 border-b border-border-default py-2 font-mono text-[13px] leading-5"
                                >
                                    <span className="text-text-secondary">
                                        {input.name}
                                    </span>
                                    <span>{input.type}</span>
                                </div>
                            ))}
                            <div className="flex justify-between gap-3 border-b border-border-default py-2 font-mono text-[13px] leading-5">
                                <span className="text-text-secondary">
                                    returns
                                </span>
                                <span>{task.output_type}</span>
                            </div>
                        </div>
                    </div>
                </Stage>

                <Stage
                    id="stage-code"
                    title="Code"
                    state={codeState}
                    meta={
                        run ? (
                            <>
                                <span>{plural(run.attempts_used, "attempt")}</span>
                                <span>
                                    <strong className="font-medium text-text-primary">
                                        {run.total_tokens.toLocaleString()}
                                    </strong>{" "}
                                    tokens
                                </span>
                            </>
                        ) : (
                            <span>Editable</span>
                        )
                    }
                >
                    <div
                        className={`grid gap-3 ${isZak ? "grid-cols-2 max-md:grid-cols-1" : "grid-cols-1"}`}
                    >
                        <CodeEditor
                            value={source}
                            onChange={edit}
                            language={language}
                            label={isZak ? "solution.zak" : "solution.py"}
                            disabled={busy}
                            placeholder={`${task.function_name}(…) in ${isZak ? "Zak" : "Python"}, or leave empty`}
                        />
                        {isZak && (
                            <CodeEditor
                                value={python ?? ""}
                                language="python"
                                readOnly
                                label="transpiled.py"
                                status={python ? "Transpiled" : "Not compiled yet"}
                                placeholder="Python appears here after Compile."
                            />
                        )}
                    </div>
                    {run && run.attempts.length > 0 && (
                        <AttemptTable run={run} live={polling} />
                    )}
                    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border-default pt-4">
                        <span className="text-text-secondary">
                            Leave the editor empty to let the model generate, or
                            write {isZak ? "Zak" : "Python"} yourself.
                        </span>
                        <div className="flex flex-wrap items-center gap-2 max-md:w-full">
                            <button
                                type="button"
                                className="btn btn-ghost"
                                onClick={reset}
                                disabled={busy}
                            >
                                <Icon name="reset" />
                                Reset
                            </button>
                            {isZak && (
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={compile}
                                    disabled={busy || !source.trim()}
                                >
                                    Compile
                                </button>
                            )}
                            <button
                                type="button"
                                className="btn btn-primary"
                                onClick={startRun}
                                disabled={busy}
                            >
                                {busy && !compileMutation.isPending
                                    ? "Running…"
                                    : custom
                                      ? "Run my code"
                                      : "Generate & run"}
                            </button>
                            <kbd className="kbd max-md:hidden">⌘ Enter</kbd>
                        </div>
                    </div>
                </Stage>

                <Stage
                    id="stage-compile"
                    title="Compile"
                    state={compileState}
                    summary={compileSummary}
                    meta={
                        compileState === "failed" &&
                        (compiled?.errors ?? attempt?.compile_errors)?.length ? (
                            <span>
                                {plural(
                                    (compiled?.errors ?? attempt?.compile_errors ?? [])
                                        .length,
                                    "error",
                                )}
                            </span>
                        ) : undefined
                    }
                >
                    {compileBody}
                </Stage>

                <Stage
                    id="stage-run"
                    title="Run"
                    state={runState}
                    summary={runSummary}
                    meta={tests ? <span>{tests}</span> : undefined}
                >
                    {runState === "running" && (
                        <div
                            className="relative h-1 overflow-hidden rounded-full bg-surface-raised"
                            role="progressbar"
                            aria-label="Running tests"
                        >
                            <span className="absolute inset-y-0 left-0 w-[30%] animate-slide rounded-full bg-text-action" />
                        </div>
                    )}
                </Stage>

                <Stage
                    id="stage-results"
                    title="Results"
                    state={finished ? (passed ? "done" : "failed") : "waiting"}
                    summary={finished ? undefined : "Waits for Run"}
                    last
                >
                    {finished && (
                        <>
                            <div className="flex flex-wrap items-center gap-3">
                                <StatusBadge status={run.status} solid />
                                <h3 className="text-xl font-semibold tracking-tight">
                                    {attempt?.tests_total != null
                                        ? `${attempt.tests_passed ?? 0} of ${attempt.tests_total} hidden tests passed`
                                        : attempt?.exec_outcome
                                          ? outcomeLabels[attempt.exec_outcome]
                                          : "No tests ran"}
                                </h3>
                            </div>
                            <div className="grid grid-cols-4 rounded-md border border-border-default max-md:grid-cols-2">
                                <button
                                    type="button"
                                    className="group flex flex-col items-start gap-1 rounded-md px-4 py-3 text-left transition-colors hover:bg-surface-hover"
                                    onClick={() => setArtifact(true)}
                                >
                                    <span className="label">Total tokens</span>
                                    <span className="flex items-center gap-1.5 text-xl font-medium">
                                        {run.total_tokens.toLocaleString()}
                                        <Icon
                                            name="external"
                                            size={14}
                                            className="text-icon-secondary group-hover:text-icon-primary"
                                        />
                                    </span>
                                </button>
                                <div className="flex flex-col gap-1 border-l border-border-default px-4 py-3">
                                    <span className="label">Attempts</span>
                                    <span className="text-xl font-medium">
                                        {run.attempts_used}
                                    </span>
                                </div>
                                <div className="flex flex-col gap-1 border-l border-border-default px-4 py-3 max-md:border-t max-md:border-l-0">
                                    <span className="label">Latency</span>
                                    <span className="text-xl font-medium">
                                        {(run.latency_ms_total / 1000).toFixed(2)} s
                                    </span>
                                </div>
                                <div className="flex flex-col gap-1 border-l border-border-default px-4 py-3 max-md:border-t">
                                    <span className="label">Tests</span>
                                    <span className="text-xl font-medium">
                                        {attempt?.tests_total != null
                                            ? `${attempt.tests_passed ?? 0} / ${attempt.tests_total}`
                                            : "–"}
                                    </span>
                                </div>
                            </div>
                            {attempt?.tests_total != null &&
                                attempt.tests_total > 0 && (
                                    <TestMeter
                                        passed={attempt.tests_passed ?? 0}
                                        total={attempt.tests_total}
                                    />
                                )}
                            <span className="text-text-tertiary">
                                Hidden tests are never sent to this browser.{" "}
                                <Link to="/docs">How it works</Link>
                            </span>
                        </>
                    )}
                </Stage>
            </div>

            <RecentRuns taskId={task.id} errorText={errorText} />

            {artifact && run && (
                <ArtifactDialog
                    title={`Token accounting · run #${run.id}`}
                    onClose={() => setArtifact(false)}
                >
                    <p className="text-text-secondary">
                        Token counts come from the model&apos;s own tokenizer
                        and include every attempt, repairs included.
                    </p>
                    <dl className="facts">
                        <div>
                            <dt>Prompt (including language instructions)</dt>
                            <dd>{run.prompt_tokens_total.toLocaleString()}</dd>
                        </div>
                        <div>
                            <dt>Completion</dt>
                            <dd>{run.completion_tokens_total.toLocaleString()}</dd>
                        </div>
                        <div>
                            <dt>
                                Total across {plural(run.attempts_used, "attempt")}
                            </dt>
                            <dd>{run.total_tokens.toLocaleString()}</dd>
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
                    <pre className="code-block">{source}</pre>
                </ArtifactDialog>
            )}
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

    function select(nextTaskId: string, lang: Language) {
        setParams({ task: nextTaskId, lang });
    }

    const loadError = tasks.error ?? task.error;

    const controls = (
        <div className="grid grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto] items-end gap-3 max-md:grid-cols-1">
            <label className="flex min-w-0 flex-col gap-1.5">
                <span className="label">Task</span>
                <span className="relative">
                    <select
                        className="field"
                        value={taskId ?? ""}
                        disabled={!tasks.data}
                        onChange={(event) => select(event.target.value, language)}
                    >
                        {tasks.data?.map((item) => (
                            <option key={item.id} value={item.id}>
                                {item.title}
                            </option>
                        ))}
                    </select>
                    <Icon
                        name="chevron-down"
                        className="pointer-events-none absolute top-3 right-3 text-icon-secondary"
                    />
                </span>
            </label>
            <label className="flex min-w-0 flex-col gap-1.5">
                <span className="label">Model</span>
                <span className="relative">
                    <select className="field" defaultValue="default">
                        <option value="default">{defaultModel}</option>
                    </select>
                    <Icon
                        name="chevron-down"
                        className="pointer-events-none absolute top-3 right-3 text-icon-secondary"
                    />
                </span>
            </label>
            <div className="flex flex-col gap-1.5">
                <span className="label" id="language-label">
                    Language
                </span>
                <div
                    className="inline-flex h-10 items-center gap-0.5 rounded-md border border-border-default bg-surface-page p-0.5"
                    role="group"
                    aria-labelledby="language-label"
                >
                    {(["zak", "python"] as const).map((lang) => (
                        <button
                            key={lang}
                            type="button"
                            aria-pressed={language === lang}
                            className={`h-full rounded-sm px-4 font-medium transition-colors max-md:flex-1 ${
                                language === lang
                                    ? "bg-surface-accent-subtle text-text-primary shadow-[inset_0_0_0_1px_var(--color-border-action)]"
                                    : "text-text-secondary hover:text-text-primary"
                            }`}
                            disabled={!taskId}
                            onClick={() => taskId && select(taskId, lang)}
                        >
                            {lang === "zak" ? "Zak" : "Python"}
                        </button>
                    ))}
                </div>
            </div>
        </div>
    );

    if (task.data && !loadError) {
        return (
            <PlaygroundSession
                key={`${task.data.id}-${language}`}
                task={task.data}
                language={language}
                controls={controls}
            />
        );
    }

    return (
        <>
            <PageHead />
            <Stage id="stage-task" title="Task" state="active" last>
                {controls}
                {loadError ? (
                    <p className="text-text-error" role="alert">
                        {errorText(loadError)}
                    </p>
                ) : (
                    <div className="flex items-center gap-2 text-text-secondary">
                        <Icon name="clock" />
                        Loading tasks…
                    </div>
                )}
            </Stage>
        </>
    );
}
