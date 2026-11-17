import { useState } from "react";
import Icon from "@/components/Icon";
import StatusBadge from "@/components/StatusBadge";
import type { Attempt, Language, Run } from "@/lib/benchmark";
import {
    compilerErrorText,
    formatCount,
    formatDate,
    formatLatency,
} from "@/lib/format";

/** Run facts and every attempt, shared by the run dialog and the paired comparison. */
export function RunFacts({ run }: { run: Run }) {
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
