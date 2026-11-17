import { useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { NavLink, useNavigate } from "react-router";
import Icon from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { createPair, useTasks } from "@/lib/benchmark";
import { errorText } from "@/lib/format";

const tabs = [
    { to: "/explorer/suites", label: "Suites" },
    { to: "/explorer/runs", label: "Runs" },
];

/** Explorer title, the Suites / Runs tabs and the "Run matched" action, shared by every Explorer page. */
export default function ExplorerNav({ taskId }: { taskId?: string }) {
    return (
        <div className="mb-8 flex flex-col gap-6 max-md:mb-6">
            <div className="flex items-end justify-between gap-6 max-md:flex-col max-md:items-stretch">
                <div>
                    <h1 className="text-display font-semibold tracking-tight max-md:text-title">
                        Explorer
                    </h1>
                    <p className="mt-2 text-base text-text-secondary">
                        Zak and Python side by side, then every run, attempt
                        and token.
                    </p>
                </div>
                <RunMatched initialTaskId={taskId} />
            </div>
            <nav
                className="flex gap-1 border-b border-border-default"
                aria-label="Explorer views"
            >
                {tabs.map((tab) => (
                    <NavLink
                        key={tab.to}
                        to={tab.to}
                        className={({ isActive }) =>
                            `-mb-px flex h-10 items-center border-b-2 px-3 font-medium ${
                                isActive
                                    ? "border-border-selected text-text-primary"
                                    : "border-transparent text-text-secondary hover:text-text-primary"
                            }`
                        }
                    >
                        {tab.label}
                    </NavLink>
                ))}
            </nav>
        </div>
    );
}

function RunMatched({ initialTaskId }: { initialTaskId?: string }) {
    const tasks = useTasks();
    const navigate = useNavigate();
    const queryClient = useQueryClient();
    const [picked, setPicked] = useState<string | null>(null);
    const taskId = picked ?? initialTaskId ?? tasks.data?.[0]?.id ?? "";
    const launch = useMutation({
        mutationFn: (id: string) => createPair(id),
        onSuccess: (response) => {
            queryClient.invalidateQueries({ queryKey: ["runs"] });
            navigate(`/explorer/pairs/${encodeURIComponent(response.pair_id)}`);
        },
    });

    function submit(event: FormEvent) {
        event.preventDefault();
        if (taskId) launch.mutate(taskId);
    }

    const error = launch.error;
    const message =
        error instanceof ApiError && error.status === 403
            ? error.message || "Your account can't launch runs."
            : error
              ? `Could not start a matched run. ${errorText(error)}`
              : null;

    return (
        <form
            className="flex flex-col items-end gap-2 max-md:items-stretch"
            onSubmit={submit}
        >
            <div className="flex gap-2 max-md:flex-col">
                <label className="relative max-md:w-full">
                    <span className="sr-only">Task for a matched run</span>
                    <select
                        className="field w-64 max-md:w-full"
                        value={taskId}
                        disabled={!tasks.data?.length || launch.isPending}
                        onChange={(event) => {
                            setPicked(event.target.value);
                            launch.reset();
                        }}
                    >
                        {!tasks.data && <option value="">Loading tasks…</option>}
                        {tasks.data?.map((task) => (
                            <option value={task.id} key={task.id}>
                                {task.title}
                            </option>
                        ))}
                    </select>
                    <Icon
                        name="chevron-down"
                        className="pointer-events-none absolute top-3.5 right-3 text-icon-secondary"
                    />
                </label>
                <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={!taskId || launch.isPending}
                >
                    <Icon
                        name={launch.isPending ? "spinner" : "arrow-right"}
                        className={launch.isPending ? "animate-spin" : undefined}
                    />
                    {launch.isPending ? "Starting…" : "Run matched"}
                </button>
            </div>
            {message && (
                <p
                    className="flex max-w-md items-start gap-2 text-text-error"
                    role="alert"
                >
                    <Icon name="alert" className="mt-0.5 shrink-0" />
                    {message}
                </p>
            )}
            {tasks.error && (
                <p className="text-text-error" role="alert">
                    Could not load tasks. {errorText(tasks.error)}
                </p>
            )}
        </form>
    );
}
