import { Link } from "react-router";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import { useRuns } from "@/lib/benchmark";

/** The last five runs for the selected task, linking into Explorer. */
export default function RecentRuns({
    taskId,
    errorText,
}: {
    taskId: string;
    errorText: (error: unknown) => string;
}) {
    const runs = useRuns();
    const recent = [...(runs.data ?? [])]
        .filter((run) => run.task_id === taskId)
        .sort((a, b) => b.id - a.id)
        .slice(0, 5);

    return (
        <section className="mt-10" aria-labelledby="recent-title">
            <div className="mb-3 flex items-center justify-between gap-3">
                <h2 id="recent-title" className="text-xl font-semibold tracking-tight">
                    Recent runs
                </h2>
                <Link to={`/explorer?task=${encodeURIComponent(taskId)}`}>
                    Open Explorer
                </Link>
            </div>
            {runs.error ? (
                <p className="text-text-error" role="alert">
                    {errorText(runs.error)}
                </p>
            ) : !recent.length ? (
                <div className="flex items-center gap-2 rounded-lg border border-dashed border-border-default px-4 py-4 text-text-secondary">
                    <Icon name="clock" />
                    {runs.isPending ? "Loading runs…" : "Your runs show up here."}
                </div>
            ) : (
                <div className="overflow-hidden rounded-lg border border-border-default">
                    {recent.map((run) => (
                        <Link
                            key={run.id}
                            to={`/explorer?run=${run.id}`}
                            className="grid min-h-13 grid-cols-[80px_88px_minmax(0,1fr)_auto_16px] items-center gap-3 border-t border-border-default px-4 text-text-primary no-underline first:border-t-0 hover:bg-surface-hover hover:text-text-primary max-md:grid-cols-[minmax(0,1fr)_auto] max-md:py-3"
                            aria-label={`Run ${run.id}, ${run.language}, ${run.status}`}
                        >
                            <span>#{run.id}</span>
                            <span className="text-text-secondary max-md:hidden">
                                {run.language === "zak" ? "Zak" : "Python"}
                            </span>
                            <span className="max-md:order-first max-md:col-span-2">
                                <StatusBadge status={run.status} />
                            </span>
                            <span className="text-right text-text-secondary">
                                {run.attempts_used} attempt
                                {run.attempts_used === 1 ? "" : "s"}
                            </span>
                            <Icon
                                name="chevron-right"
                                className="text-icon-secondary max-md:hidden"
                            />
                        </Link>
                    ))}
                </div>
            )}
        </section>
    );
}
