import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams } from "react-router";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import ExplorerNav from "@/components/explorer/ExplorerNav";
import { useSuite, useSuites, useTasks } from "@/lib/benchmark";
import type {
    Language,
    RunStatus,
    Suite,
    SuiteDetail,
    SuiteGroup,
    SuiteSummary,
} from "@/lib/benchmark";
import {
    errorText,
    formatCount,
    formatDate,
    formatPercent,
    formatPoints,
    formatRatio,
    languageName,
} from "@/lib/format";

const languages: Language[] = ["zak", "python"];
const head = "label h-10 px-4 text-left whitespace-nowrap";
const cell = "h-12 px-4 whitespace-nowrap tabular-nums";

/** The suite a bare /explorer/suites opens: the newest completed one, else the newest. */
function latestSuite(suites: Suite[]) {
    return suites.find((suite) => suite.status === "completed") ?? suites[0];
}

/**
 * /explorer: opens the latest suite summary when one exists, otherwise the run list.
 * Older links such as /explorer?run=12 or ?task=… keep working by going to the run list.
 */
export function ExplorerLanding() {
    const { search } = useLocation();
    const suites = useSuites();
    if (search) return <Navigate to={`/explorer/runs${search}`} replace />;
    if (suites.isPending) return <Loading text="Loading Explorer…" />;
    if (suites.data?.length)
        return <Navigate to={`/explorer/suites/${latestSuite(suites.data).id}`} replace />;
    return <Navigate to="/explorer/runs" replace />;
}

/** /explorer/suites/:suiteId: the dev-suite summary for one persisted suite run. */
export default function SuitePage() {
    const { suiteId } = useParams();
    const suites = useSuites();
    const parsed = Number(suiteId);
    const id = Number.isInteger(parsed) && parsed > 0 ? parsed : null;
    const suite = useSuite(id);

    if (suiteId === undefined) {
        if (suites.data?.length) {
            return (
                <Navigate
                    to={`/explorer/suites/${latestSuite(suites.data).id}`}
                    replace
                />
            );
        }
        return (
            <>
                <ExplorerNav />
                {suites.error ? (
                    <Empty title="Could not load suites">
                        <p className="text-text-error">
                            GET /suites failed. {errorText(suites.error)}
                        </p>
                    </Empty>
                ) : suites.isPending ? (
                    <Loading text="Loading suites…" />
                ) : (
                    <Empty title="No suite runs yet">
                        <p className="text-text-secondary">
                            Suites run with{" "}
                            <code className="font-mono text-[13px]">
                                zakbench run --persist
                            </code>{" "}
                            show up here.
                        </p>
                        <Link to="/explorer/runs" className="btn btn-secondary">
                            See your runs
                        </Link>
                    </Empty>
                )}
            </>
        );
    }

    return (
        <>
            <ExplorerNav />
            <SuitePicker suites={suites.data ?? []} current={id} />
            {suite.error ? (
                <Empty title="Could not load this suite">
                    <p className="text-text-error">
                        GET /suites/{suiteId} failed. {errorText(suite.error)}
                    </p>
                </Empty>
            ) : !suite.data ? (
                <Loading text="Loading suite…" />
            ) : (
                <SuiteBody suite={suite.data} />
            )}
        </>
    );
}

function SuitePicker({
    suites,
    current,
}: {
    suites: Suite[];
    current: number | null;
}) {
    const navigate = useNavigate();
    if (suites.length < 2) return null;
    return (
        <label className="relative mb-6 inline-block max-md:w-full">
            <span className="sr-only">Suite run</span>
            <select
                className="field w-auto max-md:w-full"
                value={current ?? ""}
                onChange={(event) =>
                    navigate(`/explorer/suites/${event.target.value}`)
                }
            >
                {suites.map((suite) => (
                    <option value={suite.id} key={suite.id}>
                        #{suite.id} · {suite.suite} · {suite.model_name} ·{" "}
                        {formatDate(suite.created_at)} · {suite.status}
                    </option>
                ))}
            </select>
            <Icon
                name="chevron-down"
                className="pointer-events-none absolute top-3.5 right-3 text-icon-secondary"
            />
        </label>
    );
}

function SuiteBody({ suite }: { suite: SuiteDetail }) {
    const summary = suite.summary;
    return (
        <>
            <div className="mb-6 flex flex-col gap-2">
                <p className="label">Suite summary</p>
                <h2 className="text-title font-semibold tracking-tight max-md:text-xl">
                    {suite.suite} suite · {suite.model_name}
                </h2>
                <p className="text-text-tertiary">
                    Suite #{suite.id} · seed {suite.seed} · prompt{" "}
                    {suite.prompt_version} · spec {suite.spec_version ?? "–"} ·
                    up to {suite.max_attempts} attempts · finished{" "}
                    {formatDate(suite.finished_at)}
                </p>
            </div>
            {suite.status === "running" ? (
                <Notice>
                    <Icon name="spinner" className="animate-spin" />
                    This suite is still running. The summary appears once
                    every task has both runs.
                </Notice>
            ) : !summary ? (
                <Notice>
                    <Icon name="alert" />
                    This suite stopped before it finished ({suite.status}), so
                    it has no summary.
                </Notice>
            ) : (
                <>
                    <Overview summary={summary} />
                    <CategoryTable summary={summary} />
                    <TaskTable summary={summary} pairs={suite.pairs} />
                </>
            )}
        </>
    );
}

function Overview({ summary }: { summary: SuiteSummary }) {
    const overall = summary.overall;
    const k = summary.max_attempts;
    const both = overall.paired.tasks.length;
    return (
        <section className="mb-10">
            <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
                {languages.map((language) => {
                    const stats = overall.languages[language];
                    const tokens = overall.paired[language];
                    return (
                        <div
                            key={language}
                            className="flex flex-col gap-4 rounded-lg border border-border-default bg-surface-default p-5"
                        >
                            <h3 className="text-xl font-semibold tracking-tight">
                                {languageName(language)}
                            </h3>
                            <div className="flex gap-8">
                                <Stat label="pass@1" value={formatPercent(stats.pass_at_1)} />
                                <Stat label={`pass@${k}`} value={formatPercent(stats.pass_at_k)} />
                            </div>
                            <dl className="facts">
                                <div>
                                    <dt>Runs passed</dt>
                                    <dd className="tabular-nums">
                                        {stats.passed} / {stats.runs}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Mean total tokens</dt>
                                    <dd className="tabular-nums">
                                        {formatCount(tokens.mean_total_tokens)}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Median total tokens</dt>
                                    <dd className="tabular-nums">
                                        {formatCount(tokens.median_total_tokens)}
                                    </dd>
                                </div>
                                <div>
                                    <dt>Harness errors</dt>
                                    <dd className="tabular-nums">{stats.errors}</dd>
                                </div>
                            </dl>
                        </div>
                    );
                })}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-4 rounded-lg border border-border-default p-5 max-md:grid-cols-1">
                <Stat
                    label="Zak / Python tokens"
                    value={formatRatio(overall.paired.token_ratio)}
                    note={`Summed over the ${both} of ${overall.tasks} tasks both languages solved. Below 1× means Zak used fewer.`}
                />
                <Stat
                    label={`Correctness gap (pass@${k})`}
                    value={formatPoints(overall.correctness_gap)}
                    note="Zak minus Python. A minus sign means Zak solved fewer."
                />
            </div>
        </section>
    );
}

function CategoryTable({ summary }: { summary: SuiteSummary }) {
    const k = summary.max_attempts;
    const rows = Object.entries(summary.by_category);
    return (
        <section className="mb-10">
            <h3 className="mb-4 text-xl font-semibold tracking-tight">
                By category
            </h3>
            <div className="overflow-x-auto rounded-lg border border-border-default">
                <table className="w-full min-w-[760px] border-collapse">
                    <thead className="border-b border-border-default bg-surface-default">
                        <tr>
                            <th className={head}>Category</th>
                            <th className={`${head} text-right`}>Tasks</th>
                            <th className={`${head} text-right`}>Zak pass@{k}</th>
                            <th className={`${head} text-right`}>Python pass@{k}</th>
                            <th className={`${head} text-right`}>Gap</th>
                            <th className={`${head} text-right`}>Zak mean tokens</th>
                            <th className={`${head} text-right`}>Python mean tokens</th>
                            <th className={`${head} text-right`}>Zak / Python</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map(([category, group]) => (
                            <tr
                                key={category}
                                className="border-b border-border-default last:border-b-0"
                            >
                                <td className={cell}>{category}</td>
                                <td className={`${cell} text-right`}>{group.tasks}</td>
                                <td className={`${cell} text-right`}>
                                    {formatPercent(group.languages.zak.pass_at_k)}
                                </td>
                                <td className={`${cell} text-right`}>
                                    {formatPercent(group.languages.python.pass_at_k)}
                                </td>
                                <td className={`${cell} text-right`}>
                                    {formatPoints(group.correctness_gap)}
                                </td>
                                <td className={`${cell} text-right`}>
                                    {formatCount(group.paired.zak.mean_total_tokens)}
                                </td>
                                <td className={`${cell} text-right`}>
                                    {formatCount(group.paired.python.mean_total_tokens)}
                                </td>
                                <td className={`${cell} text-right font-medium`}>
                                    {formatRatio(group.paired.token_ratio)}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

interface TaskRow {
    taskId: string;
    category: string;
    outcome: Record<Language, RunStatus>;
    ratio: number | null;
}

/** One row per task, rebuilt from the summary's solved lists and error list. */
function taskRows(summary: SuiteSummary): TaskRow[] {
    const errored = new Set(
        summary.errors.map((error) => `${error.task_id}:${error.language}`),
    );
    const rows: TaskRow[] = [];
    for (const [category, group] of Object.entries(summary.by_category)) {
        for (const taskId of groupTasks(group)) {
            const solved = {
                zak:
                    group.paired.tasks.includes(taskId) ||
                    group.solved_by_zak_only.includes(taskId),
                python:
                    group.paired.tasks.includes(taskId) ||
                    group.solved_by_python_only.includes(taskId),
            };
            const outcome = (language: Language): RunStatus =>
                solved[language]
                    ? "passed"
                    : errored.has(`${taskId}:${language}`)
                      ? "error"
                      : "failed";
            rows.push({
                taskId,
                category,
                outcome: { zak: outcome("zak"), python: outcome("python") },
                ratio: group.paired.token_ratio_by_task[taskId] ?? null,
            });
        }
    }
    return rows.sort((a, b) => a.taskId.localeCompare(b.taskId));
}

function groupTasks(group: SuiteGroup) {
    return [
        ...group.paired.tasks,
        ...group.solved_by_zak_only,
        ...group.solved_by_python_only,
        ...group.solved_by_neither,
    ];
}

function TaskTable({
    summary,
    pairs,
}: {
    summary: SuiteSummary;
    pairs: Record<string, string> | undefined;
}) {
    const tasks = useTasks();
    const titles = new Map((tasks.data ?? []).map((task) => [task.id, task.title]));
    const rows = taskRows(summary);
    return (
        <section>
            <h3 className="mb-1 text-xl font-semibold tracking-tight">Tasks</h3>
            <p className="mb-4 text-text-secondary">
                Open a task to see its Zak and Python runs side by side.
            </p>
            <div className="overflow-x-auto rounded-lg border border-border-default">
                <table className="w-full min-w-[760px] border-collapse">
                    <thead className="border-b border-border-default bg-surface-default">
                        <tr>
                            <th className={head}>Task</th>
                            <th className={head}>Category</th>
                            <th className={head}>Zak</th>
                            <th className={head}>Python</th>
                            <th className={`${head} text-right`}>Zak / Python</th>
                            <th className={head}>
                                <span className="sr-only">Compare</span>
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((row) => {
                            const pairId = pairs?.[row.taskId];
                            const to = pairId
                                ? `/explorer/pairs/${encodeURIComponent(pairId)}`
                                : null;
                            return (
                                <tr
                                    key={row.taskId}
                                    className="border-b border-border-default last:border-b-0 hover:bg-surface-hover"
                                >
                                    <td className={cell}>
                                        {to ? (
                                            <Link
                                                to={to}
                                                className="flex flex-col items-start rounded-sm"
                                            >
                                                {titles.get(row.taskId) ?? row.taskId}
                                                <small className="text-xs text-text-tertiary">
                                                    {row.taskId}
                                                </small>
                                            </Link>
                                        ) : (
                                            <span className="flex flex-col items-start">
                                                {titles.get(row.taskId) ?? row.taskId}
                                                <small className="text-xs text-text-tertiary">
                                                    {row.taskId}
                                                </small>
                                            </span>
                                        )}
                                    </td>
                                    <td className={`${cell} text-text-secondary`}>
                                        {row.category}
                                    </td>
                                    <td className={cell}>
                                        <StatusBadge status={row.outcome.zak} />
                                    </td>
                                    <td className={cell}>
                                        <StatusBadge status={row.outcome.python} />
                                    </td>
                                    <td className={`${cell} text-right`}>
                                        {formatRatio(row.ratio)}
                                    </td>
                                    <td className={`${cell} text-right`}>
                                        {to && (
                                            <Link
                                                to={to}
                                                className="btn btn-ghost btn-icon -mr-3"
                                                aria-label={`Compare ${row.taskId}`}
                                            >
                                                <Icon name="chevron-right" />
                                            </Link>
                                        )}
                                    </td>
                                </tr>
                            );
                        })}
                    </tbody>
                </table>
            </div>
        </section>
    );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
    return (
        <div className="flex flex-col gap-1">
            <span className="label">{label}</span>
            <span className="text-title font-semibold tracking-tight tabular-nums">
                {value}
            </span>
            {note && <span className="text-sm text-text-secondary">{note}</span>}
        </div>
    );
}

function Notice({ children }: { children: ReactNode }) {
    return (
        <p
            className="flex items-center gap-2 rounded-lg border border-border-default p-5 text-text-secondary"
            role="status"
        >
            {children}
        </p>
    );
}

function Loading({ text }: { text: string }) {
    return (
        <div className="flex flex-col items-center gap-3 px-6 py-12 text-center text-text-secondary">
            <Icon name="clock" size={24} />
            <p>{text}</p>
        </div>
    );
}

function Empty({ title, children }: { title: string; children: ReactNode }) {
    return (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-border-default px-6 py-12 text-center">
            <h2 className="text-base font-semibold">{title}</h2>
            {children}
        </div>
    );
}
