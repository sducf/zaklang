import { useState } from "react";
import { useQueries, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router";
import ArtifactDialog from "@/components/ArtifactDialog";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import { ApiError } from "@/lib/api";
import {
    runQueryOptions,
    terminalStatuses,
    useRun,
    useRuns,
    useTasks,
} from "@/lib/benchmark";
import type {
    Attempt,
    CompilerError,
    Language,
    Run,
    RunStatus,
} from "@/lib/benchmark";

const pageSize = 25;
const languages: Language[] = ["zak", "python"];
const outcomes: RunStatus[] = [
    "passed",
    "failed",
    "error",
    "timeout",
    "running",
    "queued",
];

/** API errors are shown as returned, prefixed with the HTTP status. */
function errorText(error: unknown) {
    if (error instanceof ApiError) return `HTTP ${error.status}: ${error.message}`;
    return error instanceof Error ? error.message : String(error);
}

function compilerErrorText(error: CompilerError) {
    return `${error.code} ${error.line}:${error.col} ${error.message}`;
}

function languageName(language: Language) {
    return language === "zak" ? "Zak" : "Python";
}

function formatDate(iso: string | null) {
    return iso ? new Date(iso).toLocaleString() : "–";
}

function formatCount(value: number | null) {
    return value === null ? "–" : value.toLocaleString();
}

function formatLatency(ms: number | null) {
    return ms === null ? "–" : `${(ms / 1000).toFixed(2)} s`;
}

function downloadCsv(rows: string[][], filename: string) {
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
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
}

export default function ExplorerPage() {
    const queryClient = useQueryClient();
    const [params, setParams] = useSearchParams();
    const [limit, setLimit] = useState(pageSize);
    const [exporting, setExporting] = useState(false);
    const [exportError, setExportError] = useState<unknown>(null);
    const runs = useRuns();
    const tasks = useTasks();

    const languageParam = params.get("lang");
    const language = languages.find((item) => item === languageParam);
    const outcomeParam = params.get("outcome");
    const outcome = outcomes.find((item) => item === outcomeParam);
    const taskId = params.get("task") || undefined;
    const runParam = Number(params.get("run"));
    const selectedRunId =
        Number.isInteger(runParam) && runParam > 0 ? runParam : null;

    const titles = new Map(
        (tasks.data ?? []).map((item) => [item.id, item.title]),
    );
    const allRuns = [...(runs.data ?? [])].sort((a, b) => b.id - a.id);
    const taskIds = [
        ...new Set([
            ...(tasks.data ?? []).map((item) => item.id),
            ...allRuns.map((run) => run.task_id),
        ]),
    ];
    const filtered = allRuns.filter(
        (run) =>
            (!language || run.language === language) &&
            (!taskId || run.task_id === taskId) &&
            (!outcome || run.status === outcome),
    );
    const visible = filtered.slice(0, limit);
    // GET /runs has no tokens or dates, so each visible row loads its run.
    const details = useQueries({
        queries: visible.map((run) => runQueryOptions(run.id)),
    });
    const filtersActive = Boolean(language || taskId || outcome);

    function setParam(key: string, value: string | null) {
        setParams(
            (current) => {
                const next = new URLSearchParams(current);
                if (value) next.set(key, value);
                else next.delete(key);
                return next;
            },
            { replace: key !== "run" },
        );
    }

    function setFilter(key: string, value: string) {
        setLimit(pageSize);
        setParam(key, value === "all" ? null : value);
    }

    function clearFilters() {
        setLimit(pageSize);
        setParams(
            (current) => {
                const next = new URLSearchParams(current);
                ["lang", "task", "outcome"].forEach((key) => next.delete(key));
                return next;
            },
            { replace: true },
        );
    }

    async function exportCsv() {
        setExporting(true);
        setExportError(null);
        try {
            // Reuse cached details only for finished runs, and load the rest a few at a time.
            const full: Run[] = [];
            for (let start = 0; start < filtered.length; start += 6) {
                const batch = filtered.slice(start, start + 6).map((run) => {
                    const options = runQueryOptions(run.id);
                    const cached = queryClient.getQueryData(options.queryKey);
                    return cached && terminalStatuses.has(cached.status)
                        ? cached
                        : queryClient.fetchQuery(options);
                });
                // A run can finish between the list refresh and the export.
                full.push(
                    ...(await Promise.all(batch)).filter(
                        (run) => !outcome || run.status === outcome,
                    ),
                );
            }
            downloadCsv(
                [
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
                    ...full.map((run) => [
                        String(run.id),
                        run.task_id,
                        run.language,
                        run.model_name,
                        "", // The API does not record a seed yet.
                        run.status,
                        String(run.prompt_tokens_total),
                        String(run.completion_tokens_total),
                        String(run.total_tokens),
                        run.started_at,
                        "api",
                    ]),
                ],
                "zakbench-runs.csv",
            );
        } catch (error) {
            setExportError(error);
        } finally {
            setExporting(false);
        }
    }

    const head = "label h-10 px-4 text-left whitespace-nowrap";
    const cell = "h-13 px-4 whitespace-nowrap";
    const select = "relative max-md:w-full";
    const chevron =
        "pointer-events-none absolute top-3 right-3 text-icon-secondary";

    return (
        <>
            <div className="mb-10 flex items-end justify-between gap-6 max-md:mb-6 max-md:flex-col max-md:items-stretch">
                <div>
                    <h1 className="text-display font-semibold tracking-tight max-md:text-title">
                        Explorer
                    </h1>
                    <p className="mt-2 text-base text-text-secondary">
                        Every run you made, every attempt, every token.
                    </p>
                </div>
                <Link
                    className="btn btn-primary"
                    to={taskId ? `/playground?task=${taskId}` : "/playground"}
                >
                    <Icon name="plus" />
                    New playground run
                </Link>
            </div>
            <div className="mb-4 flex items-end justify-between gap-4 max-md:flex-col max-md:items-stretch">
                <div>
                    <h2 className="text-xl font-semibold tracking-tight">
                        Run history
                    </h2>
                    <p className="mt-1 text-text-secondary">
                        Open a run to see the source and accounting behind it.
                    </p>
                </div>
                <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={exportCsv}
                    disabled={!filtered.length || exporting}
                >
                    <Icon name="download" />
                    {exporting ? "Exporting…" : "Export CSV"}
                </button>
            </div>
            {exportError !== null && (
                <p className="mb-3 text-text-error" role="alert">
                    CSV export failed. {errorText(exportError)}
                </p>
            )}
            <div
                className="mb-3 flex flex-wrap items-center gap-2"
                role="group"
                aria-label="Filters"
            >
                <label className={select}>
                    <select
                        className="field w-auto max-md:w-full"
                        aria-label="Filter by language"
                        value={language ?? "all"}
                        onChange={(event) =>
                            setFilter("lang", event.target.value)
                        }
                    >
                        <option value="all">All languages</option>
                        {languages.map((item) => (
                            <option value={item} key={item}>
                                {languageName(item)}
                            </option>
                        ))}
                    </select>
                    <Icon name="chevron-down" className={chevron} />
                </label>
                <label className={select}>
                    <select
                        className="field w-auto max-md:w-full"
                        aria-label="Filter by task"
                        value={taskId ?? "all"}
                        onChange={(event) =>
                            setFilter("task", event.target.value)
                        }
                    >
                        <option value="all">All tasks</option>
                        {taskId && !taskIds.includes(taskId) && (
                            <option value={taskId}>{taskId}</option>
                        )}
                        {taskIds.map((id) => (
                            <option value={id} key={id}>
                                {titles.get(id) ?? id}
                            </option>
                        ))}
                    </select>
                    <Icon name="chevron-down" className={chevron} />
                </label>
                <label className={select}>
                    <select
                        className="field w-auto max-md:w-full"
                        aria-label="Filter by outcome"
                        value={outcome ?? "all"}
                        onChange={(event) =>
                            setFilter("outcome", event.target.value)
                        }
                    >
                        <option value="all">All outcomes</option>
                        {outcomes.map((item) => (
                            <option value={item} key={item}>
                                {item}
                            </option>
                        ))}
                    </select>
                    <Icon name="chevron-down" className={chevron} />
                </label>
                {filtersActive && (
                    <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={clearFilters}
                    >
                        Clear filters
                    </button>
                )}
                <span className="label ml-auto max-md:ml-0">
                    {filtered.length === allRuns.length
                        ? `${allRuns.length} runs`
                        : `${filtered.length} of ${allRuns.length} runs`}
                </span>
            </div>
            <div className="overflow-hidden rounded-lg border border-border-default">
                {visible.length > 0 && (
                    <div className="relative overflow-x-auto">
                        <table className="w-full min-w-[760px] border-collapse">
                            <thead className="border-b border-border-default bg-surface-default">
                                <tr>
                                    <th className={head}>Run</th>
                                    <th className={head}>Task</th>
                                    <th className={head}>Language</th>
                                    <th className={head}>Status</th>
                                    <th className={`${head} text-right`}>
                                        Attempts
                                    </th>
                                    <th className={`${head} text-right`}>
                                        Total tokens
                                    </th>
                                    <th className={head}>Date</th>
                                    <th className={head}>
                                        <span className="sr-only">Details</span>
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {visible.map((run, index) => {
                                    const detail = details[index];
                                    const open = () =>
                                        setParam("run", String(run.id));
                                    const pending = detail?.isPending ?? true;
                                    const detailError = detail?.error
                                        ? errorText(detail.error)
                                        : null;
                                    return (
                                        <tr
                                            key={run.id}
                                            className="border-b border-border-default last:border-b-0 hover:bg-surface-hover"
                                        >
                                            <td
                                                className={`${cell} text-text-secondary`}
                                            >
                                                #{run.id}
                                            </td>
                                            <td className={cell}>
                                                <button
                                                    type="button"
                                                    className="flex flex-col items-start rounded-sm text-left"
                                                    onClick={open}
                                                >
                                                    {titles.get(run.task_id) ??
                                                        run.task_id}
                                                    <small className="text-xs text-text-tertiary">
                                                        {run.task_id}
                                                    </small>
                                                </button>
                                            </td>
                                            <td
                                                className={`${cell} text-text-secondary`}
                                            >
                                                {languageName(run.language)}
                                            </td>
                                            <td className={cell}>
                                                <StatusBadge
                                                    status={run.status}
                                                />
                                            </td>
                                            <td
                                                className={`${cell} text-right`}
                                            >
                                                {run.attempts_used}
                                            </td>
                                            <td
                                                className={`${cell} text-right`}
                                            >
                                                {detail?.data ? (
                                                    <button
                                                        type="button"
                                                        className="rounded-sm text-text-action hover:text-text-action-hover"
                                                        onClick={open}
                                                    >
                                                        {detail.data.total_tokens.toLocaleString()}
                                                    </button>
                                                ) : (
                                                    <span
                                                        className="text-text-tertiary"
                                                        title={
                                                            detailError ??
                                                            undefined
                                                        }
                                                    >
                                                        {pending ? "…" : "!"}
                                                    </span>
                                                )}
                                            </td>
                                            <td
                                                className={`${cell} text-text-secondary`}
                                            >
                                                {detail?.data
                                                    ? formatDate(
                                                          detail.data
                                                              .started_at,
                                                      )
                                                    : pending
                                                      ? "…"
                                                      : "!"}
                                            </td>
                                            <td className={`${cell} text-right`}>
                                                <button
                                                    type="button"
                                                    className="btn btn-ghost btn-icon -mr-3"
                                                    aria-label={`Inspect run ${run.id}`}
                                                    onClick={open}
                                                >
                                                    <Icon name="chevron-right" />
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
                {runs.error ? (
                    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                        <h3 className="text-base font-semibold">
                            Could not load runs
                        </h3>
                        <p className="text-text-error">
                            GET /runs failed. {errorText(runs.error)}
                        </p>
                        <button
                            type="button"
                            className="btn btn-secondary"
                            onClick={() => runs.refetch()}
                        >
                            Try again
                        </button>
                    </div>
                ) : runs.isPending ? (
                    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center text-text-secondary">
                        <Icon name="clock" size={24} />
                        <p>Loading runs…</p>
                    </div>
                ) : !allRuns.length ? (
                    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                        <Icon
                            name="clock"
                            size={24}
                            className="text-icon-secondary"
                        />
                        <h3 className="text-base font-semibold">No runs yet</h3>
                        <p className="text-text-secondary">
                            Runs you start in the Playground show up here.
                        </p>
                        <Link to="/playground" className="btn btn-secondary">
                            Open Playground
                        </Link>
                    </div>
                ) : (
                    !filtered.length && (
                        <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
                            <h3 className="text-base font-semibold">
                                No runs match these filters
                            </h3>
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={clearFilters}
                            >
                                Clear filters
                            </button>
                        </div>
                    )
                )}
            </div>
            {filtered.length > visible.length && (
                <div className="mt-3 flex justify-center">
                    <button
                        type="button"
                        className="btn btn-ghost"
                        onClick={() => setLimit(limit + pageSize)}
                    >
                        Show {Math.min(pageSize, filtered.length - limit)} more
                    </button>
                </div>
            )}
            {selectedRunId !== null && (
                <RunDetail
                    runId={selectedRunId}
                    titles={titles}
                    onClose={() => setParam("run", null)}
                />
            )}
        </>
    );
}

function RunDetail({
    runId,
    titles,
    onClose,
}: {
    runId: number;
    titles: Map<string, string>;
    onClose: () => void;
}) {
    const query = useRun(runId);
    const run = query.data;
    const title = run
        ? `Run #${run.id} · ${titles.get(run.task_id) ?? run.task_id} · ${languageName(run.language)}`
        : `Run #${runId}`;

    return (
        <ArtifactDialog title={title} onClose={onClose}>
            {query.error ? (
                <p className="text-text-error">
                    GET /runs/{runId} failed. {errorText(query.error)}
                </p>
            ) : !run ? (
                <p className="text-text-secondary">Loading run…</p>
            ) : (
                <RunFacts run={run} />
            )}
        </ArtifactDialog>
    );
}

function RunFacts({ run }: { run: Run }) {
    return (
        <>
            <dl className="facts">
                <div>
                    <dt>Task</dt>
                    <dd>{run.task_id}</dd>
                </div>
                <div>
                    <dt>Status</dt>
                    <dd>
                        <StatusBadge status={run.status} />
                    </dd>
                </div>
                <div>
                    <dt>Model / temperature</dt>
                    <dd>
                        {run.model_name} / {run.temperature ?? "–"}
                    </dd>
                </div>
                <div>
                    <dt>Attempts used</dt>
                    <dd>{run.attempts_used}</dd>
                </div>
                <div>
                    <dt>Prompt / completion / total tokens</dt>
                    <dd>
                        {run.prompt_tokens_total.toLocaleString()} /{" "}
                        {run.completion_tokens_total.toLocaleString()} /{" "}
                        {run.total_tokens.toLocaleString()}
                    </dd>
                </div>
                <div>
                    <dt>Total latency</dt>
                    <dd>{formatLatency(run.latency_ms_total)}</dd>
                </div>
                <div>
                    <dt>Started / completed</dt>
                    <dd>
                        {formatDate(run.started_at)} /{" "}
                        {formatDate(run.completed_at)}
                    </dd>
                </div>
            </dl>
            {run.attempts.length === 0 && (
                <p className="text-text-secondary">No attempts recorded yet.</p>
            )}
            {run.attempts.map((attempt) => (
                <AttemptCard
                    attempt={attempt}
                    language={run.language}
                    key={attempt.index}
                />
            ))}
        </>
    );
}

function AttemptCard({
    attempt,
    language,
}: {
    attempt: Attempt;
    language: Language;
}) {
    const [completionOpen, setCompletionOpen] = useState(false);
    const [promptNote, setPromptNote] = useState(false);
    const compile =
        attempt.compile_ok === null
            ? language === "zak"
                ? "not compiled"
                : "n/a"
            : attempt.compile_ok
              ? "ok"
              : "failed";
    const tests =
        attempt.tests_total === null
            ? "–"
            : `${attempt.tests_passed ?? 0} / ${attempt.tests_total}`;
    const numberLink =
        "rounded-sm text-text-action hover:text-text-action-hover";

    return (
        <section className="flex flex-col gap-3 rounded-lg border border-border-default p-4">
            <h3 className="flex items-center justify-between gap-3 text-base font-semibold">
                Attempt {attempt.index}
                <span className="text-sm font-normal text-text-secondary">
                    {attempt.exec_outcome ?? "not run"}
                </span>
            </h3>
            <dl className="facts">
                <div>
                    <dt>Prompt tokens</dt>
                    <dd>
                        <button
                            type="button"
                            className={numberLink}
                            onClick={() => setPromptNote(!promptNote)}
                        >
                            {formatCount(attempt.prompt_tokens)}
                        </button>
                    </dd>
                </div>
                <div>
                    <dt>Completion tokens</dt>
                    <dd>
                        <button
                            type="button"
                            className={numberLink}
                            onClick={() => setCompletionOpen(true)}
                        >
                            {formatCount(attempt.completion_tokens)}
                        </button>
                    </dd>
                </div>
                <div>
                    <dt>Total tokens</dt>
                    <dd>{formatCount(attempt.total_tokens)}</dd>
                </div>
                <div>
                    <dt>Latency</dt>
                    <dd>{formatLatency(attempt.latency_ms)}</dd>
                </div>
                <div>
                    <dt>Compile</dt>
                    <dd>{compile}</dd>
                </div>
                <div>
                    <dt>Tests passed</dt>
                    <dd>{tests}</dd>
                </div>
                <div>
                    <dt>Execution outcome</dt>
                    <dd>{attempt.exec_outcome ?? "–"}</dd>
                </div>
            </dl>
            {promptNote && (
                <p className="text-text-secondary">
                    The prompt text is not in the API response yet, so it
                    can't be shown here.
                </p>
            )}
            {attempt.compile_errors.length > 0 && (
                <ul className="flex flex-col gap-1 font-mono text-[13px] leading-5">
                    {attempt.compile_errors.map((error, index) => (
                        <li className="text-text-error" key={index}>
                            {compilerErrorText(error)}
                        </li>
                    ))}
                </ul>
            )}
            <details
                className="group"
                open={completionOpen}
                onToggle={(event) =>
                    setCompletionOpen(event.currentTarget.open)
                }
            >
                <summary className="flex h-11 cursor-pointer items-center gap-2 font-medium [&::-webkit-details-marker]:hidden">
                    <Icon
                        name="chevron-right"
                        className="transition-transform group-open:rotate-90"
                    />
                    Completion
                </summary>
                <pre className="code-block">
                    {attempt.completion_text || "(empty)"}
                </pre>
            </details>
            {attempt.transpiled_python !== null && (
                <details className="group">
                    <summary className="flex h-11 cursor-pointer items-center gap-2 font-medium [&::-webkit-details-marker]:hidden">
                        <Icon
                            name="chevron-right"
                            className="transition-transform group-open:rotate-90"
                        />
                        Transpiled Python
                    </summary>
                    <pre className="code-block">{attempt.transpiled_python}</pre>
                </details>
            )}
        </section>
    );
}
