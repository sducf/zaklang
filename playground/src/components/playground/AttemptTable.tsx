import Icon from "@/components/Icon";
import type { Attempt, Run } from "@/lib/benchmark";

function count(value: number | null) {
    return value === null ? "–" : value.toLocaleString();
}

function seconds(ms: number | null) {
    return ms === null ? "–" : `${(ms / 1000).toFixed(2)} s`;
}

function Outcome({ attempt, live }: { attempt: Attempt; live: boolean }) {
    if (attempt.compile_ok === false) {
        return (
            <span className="badge badge-error">
                <Icon name="alert" size={14} />
                Compile error
            </span>
        );
    }
    switch (attempt.exec_outcome) {
        case "pass":
            return (
                <span className="badge badge-outline">
                    <Icon name="check" size={14} />
                    Passed
                </span>
            );
        case "fail":
        case "timeout":
        case "oom":
        case "crash": {
            const label = {
                fail: "Failed",
                timeout: "Timeout",
                oom: "Out of memory",
                crash: "Crashed",
            }[attempt.exec_outcome];
            return (
                <span className="badge badge-error">
                    <Icon
                        name={attempt.exec_outcome === "timeout" ? "clock" : "alert"}
                        size={14}
                    />
                    {label}
                </span>
            );
        }
        case "not_run":
            return <span className="badge badge-neutral">Not run</span>;
        default:
            return live ? (
                <span className="badge badge-neutral">
                    <Icon name="spinner" size={14} className="animate-spin" />
                    Running
                </span>
            ) : (
                <span className="badge badge-neutral">No outcome</span>
            );
    }
}

/** Tokens for every attempt (first try and repairs), with the running total. */
export default function AttemptTable({
    run,
    live,
}: {
    run: Run;
    live: boolean;
}) {
    const cell = "h-11 px-3 whitespace-nowrap";
    const num = `${cell} text-right`;
    const head = "label h-9 px-3 text-left whitespace-nowrap";
    return (
        <div className="overflow-x-auto rounded-md border border-border-default">
            <table className="w-full border-collapse">
                <thead className="border-b border-border-default">
                    <tr>
                        <th className={head}>Attempt</th>
                        <th className={head}>Outcome</th>
                        <th className={`${head} text-right`}>Prompt</th>
                        <th className={`${head} text-right`}>Completion</th>
                        <th className={`${head} text-right`}>Total</th>
                        <th className={`${head} text-right`}>Latency</th>
                    </tr>
                </thead>
                <tbody>
                    {run.attempts.map((attempt, i) => (
                        <tr
                            key={attempt.index}
                            className="border-b border-border-default"
                        >
                            <td className={cell}>Attempt {attempt.index}</td>
                            <td className={cell}>
                                <Outcome
                                    attempt={attempt}
                                    live={live && i === run.attempts.length - 1}
                                />
                            </td>
                            <td className={num}>{count(attempt.prompt_tokens)}</td>
                            <td className={num}>
                                {count(attempt.completion_tokens)}
                            </td>
                            <td className={num}>{count(attempt.total_tokens)}</td>
                            <td className={num}>{seconds(attempt.latency_ms)}</td>
                        </tr>
                    ))}
                </tbody>
                <tfoot className="bg-surface-page font-semibold">
                    <tr>
                        <td className={cell}>Total</td>
                        <td className={cell} />
                        <td className={num}>
                            {run.prompt_tokens_total.toLocaleString()}
                        </td>
                        <td className={num}>
                            {run.completion_tokens_total.toLocaleString()}
                        </td>
                        <td className={num}>{run.total_tokens.toLocaleString()}</td>
                        <td className={num}>{seconds(run.latency_ms_total)}</td>
                    </tr>
                </tfoot>
            </table>
        </div>
    );
}
