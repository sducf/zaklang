import { Link, useParams } from "react-router";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import ExplorerNav from "@/components/explorer/ExplorerNav";
import { terminalStatuses, usePair, useTask } from "@/lib/benchmark";
import type { Language, Run } from "@/lib/benchmark";
import {
    errorText,
    formatCount,
    formatDelta,
    formatLatency,
    formatSigned,
    languageName,
} from "@/lib/format";

const order: Language[] = ["zak", "python"];

interface Metric {
    label: string;
    value: (run: Run) => number;
    format: (value: number) => string;
    /** Signed Zak minus Python text for this metric. */
    delta: (zak: number, python: number) => string;
}

const metrics: Metric[] = [
    {
        label: "Attempts used",
        value: (run) => run.attempts_used,
        format: (value) => String(value),
        delta: (zak, python) => formatSigned(zak - python),
    },
    {
        label: "Prompt tokens",
        value: (run) => run.prompt_tokens_total,
        format: formatCount,
        delta: (zak, python) => formatDelta(zak, python),
    },
    {
        label: "Completion tokens",
        value: (run) => run.completion_tokens_total,
        format: formatCount,
        delta: (zak, python) => formatDelta(zak, python),
    },
    {
        label: "Total tokens",
        value: (run) => run.total_tokens,
        format: formatCount,
        delta: (zak, python) => formatDelta(zak, python),
    },
    {
        label: "Latency",
        value: (run) => run.latency_ms_total,
        format: formatLatency,
        delta: (zak, python) => `${formatSigned((zak - python) / 1000, 2)} s`,
    },
];

/** /explorer/pairs/:pairId: one matched Zak vs Python run, side by side. */
export default function PairPage() {
    const { pairId } = useParams();
    const pair = usePair(pairId);
    const runs = pair.data ?? [];
    const byLanguage = new Map(runs.map((run) => [run.language, run]));
    const zak = byLanguage.get("zak");
    const python = byLanguage.get("python");
    const taskId = runs[0]?.task_id;
    const task = useTask(taskId);
    const finished =
        zak !== undefined &&
        python !== undefined &&
        terminalStatuses.has(zak.status) &&
        terminalStatuses.has(python.status);

    return (
        <>
            <ExplorerNav taskId={taskId} />
            {pair.error ? (
                <div className="flex flex-col items-center gap-3 rounded-lg border border-border-default px-6 py-12 text-center">
                    <h2 className="text-base font-semibold">
                        Could not load this pair
                    </h2>
                    <p className="text-text-error">
                        GET /pairs/{pairId} failed. {errorText(pair.error)}
                    </p>
                    <Link to="/explorer/runs" className="btn btn-secondary">
                        Back to runs
                    </Link>
                </div>
            ) : pair.isPending ? (
                <div className="flex flex-col items-center gap-3 px-6 py-12 text-center text-text-secondary">
                    <Icon name="clock" size={24} />
                    <p>Loading pair…</p>
                </div>
            ) : (
                <>
                    <div className="mb-6 flex flex-col gap-2">
                        <p className="label">Paired comparison</p>
                        <h2 className="text-title font-semibold tracking-tight max-md:text-xl">
                            {task.data?.title ?? taskId}
                        </h2>
                        <p className="text-text-tertiary">
                            {taskId}
                            {zak ? ` · ${zak.model_name} · seed ${zak.seed}` : ""}
                        </p>
                        {task.data && (
                            <p className="max-w-3xl text-text-secondary">
                                {task.data.prompt}
                            </p>
                        )}
                    </div>
                    {!finished && (
                        <p
                            className="mb-4 flex items-center gap-2 text-text-secondary"
                            role="status"
                        >
                            <Icon name="spinner" className="animate-spin" />
                            Waiting for both runs to finish. This page updates
                            on its own.
                        </p>
                    )}
                    <div className="grid grid-cols-2 gap-4 max-md:grid-cols-1">
                        {order.map((language) => {
                            const run = byLanguage.get(language);
                            return run ? (
                                <RunCard run={run} key={language} />
                            ) : (
                                <section
                                    key={language}
                                    className="rounded-lg border border-border-default p-5 text-text-secondary"
                                >
                                    No {languageName(language)} run in this
                                    pair.
                                </section>
                            );
                        })}
                    </div>
                    {zak && python && (
                        <DeltaTable zak={zak} python={python} final={finished} />
                    )}
                </>
            )}
        </>
    );
}

function RunCard({ run }: { run: Run }) {
    return (
        <section className="flex flex-col gap-4 rounded-lg border border-border-default bg-surface-default p-5">
            <div className="flex items-center justify-between gap-3">
                <h3 className="text-xl font-semibold tracking-tight">
                    {languageName(run.language)}
                </h3>
                <StatusBadge status={run.status} solid />
            </div>
            {run.status === "queued" && typeof run.queue_position === "number" && (
                <p className="-mt-2 text-text-secondary" role="status">
                    Queued, #{run.queue_position} in line
                </p>
            )}
            <p className="text-display font-semibold tracking-tight tabular-nums max-md:text-title">
                {formatCount(run.total_tokens)}
                <span className="ml-2 text-base font-normal text-text-secondary">
                    total tokens
                </span>
            </p>
            <dl className="facts">
                {metrics
                    .filter((metric) => metric.label !== "Total tokens")
                    .map((metric) => (
                        <div key={metric.label}>
                            <dt>{metric.label}</dt>
                            <dd className="tabular-nums">
                                {metric.format(metric.value(run))}
                            </dd>
                        </div>
                    ))}
            </dl>
            <Link
                to={`/explorer/runs?run=${run.id}`}
                className="btn btn-secondary self-start"
            >
                Run #{run.id} details
                <Icon name="chevron-right" />
            </Link>
        </section>
    );
}

function DeltaTable({
    zak,
    python,
    final,
}: {
    zak: Run;
    python: Run;
    final: boolean;
}) {
    const head = "label h-10 px-4 text-left whitespace-nowrap";
    const cell = "h-12 px-4 whitespace-nowrap tabular-nums";
    return (
        <section className="mt-8">
            <h3 className="mb-1 text-xl font-semibold tracking-tight">
                Zak minus Python
            </h3>
            <p className="mb-4 text-text-secondary">
                A minus sign means Zak used less.
                {final ? "" : " Numbers change until both runs finish."}
            </p>
            <div className="overflow-x-auto rounded-lg border border-border-default">
                <table className="w-full min-w-[560px] border-collapse">
                    <thead className="border-b border-border-default bg-surface-default">
                        <tr>
                            <th className={head}>Metric</th>
                            <th className={`${head} text-right`}>Zak</th>
                            <th className={`${head} text-right`}>Python</th>
                            <th className={`${head} text-right`}>
                                Zak − Python
                            </th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr className="border-b border-border-default">
                            <td className={cell}>Outcome</td>
                            <td className={`${cell} text-right`}>
                                <StatusBadge status={zak.status} />
                            </td>
                            <td className={`${cell} text-right`}>
                                <StatusBadge status={python.status} />
                            </td>
                            <td className={`${cell} text-right text-text-secondary`}>
                                {outcomeNote(zak, python)}
                            </td>
                        </tr>
                        {metrics.map((metric) => {
                            const a = metric.value(zak);
                            const b = metric.value(python);
                            return (
                                <tr
                                    key={metric.label}
                                    className="border-b border-border-default last:border-b-0"
                                >
                                    <td className={cell}>{metric.label}</td>
                                    <td className={`${cell} text-right`}>
                                        {metric.format(a)}
                                    </td>
                                    <td className={`${cell} text-right`}>
                                        {metric.format(b)}
                                    </td>
                                    <td
                                        className={`${cell} text-right font-medium`}
                                    >
                                        {metric.delta(a, b)}
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

function outcomeNote(zak: Run, python: Run) {
    if (!terminalStatuses.has(zak.status) || !terminalStatuses.has(python.status))
        return "Pending";
    const zakPassed = zak.status === "passed";
    const pythonPassed = python.status === "passed";
    if (zakPassed && pythonPassed) return "Both passed";
    if (zakPassed) return "Only Zak passed";
    if (pythonPassed) return "Only Python passed";
    return "Neither passed";
}
