import type { ReactNode } from "react";
import Icon from "@/components/Icon";
import type { IconName } from "@/components/Icon";

export type StageState =
    | "done"
    | "active"
    | "running"
    | "failed"
    | "waiting"
    | "skipped";

const nodeStyles: Record<StageState, string> = {
    done: "border-surface-action bg-surface-action text-icon-on-action",
    active: "bg-surface-page border-border-focus text-icon-action",
    running: "bg-surface-page border-border-focus text-icon-action",
    failed: "bg-surface-page border-border-error text-icon-error",
    waiting: "bg-surface-page border-dashed border-border-strong text-icon-tertiary",
    skipped: "bg-surface-page border-border-strong text-icon-tertiary",
};

const nodeIcons: Partial<Record<StageState, IconName>> = {
    done: "check",
    active: "code",
    running: "spinner",
    failed: "alert",
};

/**
 * One step of the Playground pipeline: a node on the rail and a card.
 * Waiting stages show dimmed with a dashed outline, and the card fades in when it unlocks.
 */
export default function Stage({
    id,
    title,
    state,
    summary,
    meta,
    last = false,
    children,
}: {
    id: string;
    title: string;
    state: StageState;
    summary?: ReactNode;
    meta?: ReactNode;
    last?: boolean;
    children?: ReactNode;
}) {
    const waiting = state === "waiting" || state === "skipped";
    const icon = nodeIcons[state];
    return (
        <section
            className="grid grid-cols-[24px_minmax(0,1fr)] gap-x-5 max-md:grid-cols-[20px_minmax(0,1fr)] max-md:gap-x-3"
            aria-labelledby={id}
        >
            <div className="flex flex-col items-center">
                <span
                    className={`mt-6 grid size-6 place-items-center rounded-full border max-md:mt-5 max-md:size-5 ${nodeStyles[state]}`}
                >
                    {icon && (
                        <Icon
                            name={icon}
                            size={14}
                            className={state === "running" ? "animate-spin" : ""}
                        />
                    )}
                </span>
                {!last && (
                    <span
                        className={`-mb-5 mt-1 w-0.5 flex-1 ${
                            state === "done"
                                ? "bg-surface-action"
                                : "bg-border-default"
                        }`}
                    />
                )}
            </div>
            <div
                key={waiting ? "waiting" : "open"}
                className={`stage-card mt-3 mb-2 rounded-lg border ${
                    waiting
                        ? "border-dashed border-border-default"
                        : "unlocked border-border-default bg-surface-default"
                }`}
            >
                <div className="flex min-h-15 flex-wrap items-center gap-x-3 gap-y-2 px-5 py-3 max-md:min-h-14 max-md:px-4">
                    <h2
                        id={id}
                        className={`text-base font-semibold ${
                            waiting ? "text-text-tertiary" : ""
                        }`}
                    >
                        {title}
                    </h2>
                    {summary && (
                        <span
                            className={
                                state === "failed"
                                    ? "text-text-error"
                                    : "text-text-tertiary"
                            }
                        >
                            {summary}
                        </span>
                    )}
                    {meta && (
                        <div className="ml-auto flex flex-wrap items-center gap-4 text-xs font-medium text-text-secondary max-md:ml-0 max-md:w-full max-md:gap-3">
                            {meta}
                        </div>
                    )}
                </div>
                {children && (
                    <div className="flex flex-col gap-4 px-5 pb-5 max-md:px-4 max-md:pb-4">
                        {children}
                    </div>
                )}
            </div>
        </section>
    );
}
