import { queryOptions, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

// Types mirror backend/api/schemas/benchmark.py (SD-30).
export type Language = "zak" | "python";
export type RunStatus =
    | "queued"
    | "running"
    | "passed"
    | "failed"
    | "error"
    | "timeout";

export interface TaskInput {
    name: string;
    type: string;
}

export interface Task {
    id: string;
    title: string;
    category: string;
    prompt: string;
    function_name: string;
    inputs: TaskInput[];
    output_type: string;
}

export interface CompilerError {
    line: number;
    col: number;
    code: string;
    message: string;
}

export interface CompileResponse {
    ok: boolean;
    errors: CompilerError[];
    python: string | null;
}

export interface PairCreateResponse {
    pair_id: string;
    run_ids: number[];
}

export interface RunCreateRequest {
    task_id: string;
    language: Language;
    source?: string;
}

export type ExecutionOutcome =
    | "pass"
    | "fail"
    | "timeout"
    | "oom"
    | "crash"
    | "not_run";

export interface Attempt {
    index: number;
    completion_text: string;
    prompt_tokens: number | null;
    completion_tokens: number | null;
    total_tokens: number | null;
    latency_ms: number | null;
    compile_ok: boolean | null;
    compile_errors: CompilerError[];
    transpiled_python: string | null;
    tests_passed: number | null;
    tests_total: number | null;
    exec_outcome: ExecutionOutcome | null;
}

export interface Run {
    id: number;
    pair_id: string | null;
    task_id: string;
    language: Language;
    model_name: string;
    temperature: number | null;
    seed: number;
    spec_version: string | null;
    prompt_version: string;
    max_attempts: number;
    started_at: string;
    completed_at: string | null;
    status: RunStatus;
    /** Place in the GPU queue while queued (SD-53), 1 = next. */
    queue_position: number | null;
    attempts_used: number;
    prompt_tokens_total: number;
    completion_tokens_total: number;
    total_tokens: number;
    latency_ms_total: number;
    attempts: Attempt[];
}

export interface RunListItem {
    id: number;
    pair_id: string | null;
    task_id: string;
    language: Language;
    seed: number;
    spec_version: string | null;
    prompt_version: string;
    max_attempts: number;
    status: RunStatus;
    attempts_used: number;
}

// The API picks the model until it exposes a models endpoint.
export const defaultModel = "Llama 3.1 8B Instruct";

export const terminalStatuses: ReadonlySet<RunStatus> = new Set([
    "passed",
    "failed",
    "error",
    "timeout",
]);

export function signature(task: Task) {
    const params = task.inputs
        .map((input) => `${input.name}: ${input.type}`)
        .join(", ");
    return `${task.function_name}(${params}) → ${task.output_type}`;
}

export function useTasks() {
    return useQuery({
        queryKey: ["tasks"],
        queryFn: () => api<Task[]>("/tasks"),
    });
}

export function useTask(taskId: string | undefined) {
    return useQuery({
        queryKey: ["tasks", taskId],
        queryFn: () => api<Task>(`/tasks/${encodeURIComponent(taskId!)}`),
        enabled: taskId !== undefined,
    });
}

export function compileZak(source: string) {
    return api<CompileResponse>("/compile", {
        method: "POST",
        body: JSON.stringify({ source }),
    });
}

export function createRun(request: RunCreateRequest) {
    return api<Run>("/runs", {
        method: "POST",
        body: JSON.stringify(request),
    });
}

/** GET /runs/{id}, polled every second until the run reaches a terminal status. */
export function runQueryOptions(runId: number | null) {
    return queryOptions({
        queryKey: ["run", runId],
        queryFn: () => api<Run>(`/runs/${runId}`),
        enabled: runId !== null,
        refetchInterval: (query) => {
            const status = query.state.data?.status;
            if (query.state.error || (status && terminalStatuses.has(status)))
                return false;
            return 1000;
        },
    });
}

export function useRun(runId: number | null) {
    return useQuery(runQueryOptions(runId));
}

/** The current user's runs, newest first. Re-checked while any run is unfinished. */
export function useRuns() {
    return useQuery({
        queryKey: ["runs"],
        queryFn: () => api<RunListItem[]>("/runs"),
        refetchInterval: (query) =>
            query.state.data?.some((run) => !terminalStatuses.has(run.status))
                ? 2000
                : false,
    });
}

/** POST /runs/pair: queue one Zak run and one Python run for the same task. */
export function createPair(taskId: string) {
    return api<PairCreateResponse>("/runs/pair", {
        method: "POST",
        body: JSON.stringify({ task_id: taskId }),
    });
}

/** GET /pairs/{id}, polled every second until both runs reach a terminal status. */
export function usePair(pairId: string | undefined) {
    return useQuery({
        queryKey: ["pair", pairId],
        queryFn: () => api<Run[]>(`/pairs/${encodeURIComponent(pairId!)}`),
        enabled: pairId !== undefined,
        refetchInterval: (query) => {
            const runs = query.state.data;
            if (query.state.error) return false;
            if (runs && runs.length > 0 && runs.every((run) => terminalStatuses.has(run.status)))
                return false;
            return 1000;
        },
    });
}

// Types mirror SuiteResponse / SuiteDetailResponse and zakbench/evaluation/summary.py (SD-57).
export type SuiteStatus = "running" | "completed" | "failed" | (string & {});

export interface Suite {
    id: number;
    cli_suite_run_id: string;
    suite: string;
    model_name: string;
    seed: number;
    prompt_version: string;
    spec_version: string | null;
    max_attempts: number;
    status: SuiteStatus;
    created_at: string;
    finished_at: string | null;
}

export interface LanguageStats {
    runs: number;
    passed: number;
    errors: number;
    pass_at_1: number | null;
    pass_at_k: number | null;
    total_tokens: number;
    repair_token_share: number | null;
}

export interface TokenStats {
    mean_total_tokens: number | null;
    median_total_tokens: number | null;
}

export interface SuiteGroup {
    tasks: number;
    languages: Record<Language, LanguageStats>;
    correctness_gap: number;
    paired: {
        tasks: string[];
        zak: TokenStats;
        python: TokenStats;
        token_ratio: number | null;
        token_ratio_by_task: Record<string, number | null>;
    };
    solved_by_zak_only: string[];
    solved_by_python_only: string[];
    solved_by_neither: string[];
}

export interface SuiteSummary {
    suite: string;
    suite_run_id: string;
    model_id: string;
    spec_version: string | null;
    prompt_version: string;
    seed: number;
    temperature: number | null;
    max_tokens: number;
    max_attempts: number;
    overall: SuiteGroup;
    by_category: Record<string, SuiteGroup>;
    errors: { task_id: string; language: Language; error: string | null }[];
}

export interface SuiteDetail extends Suite {
    summary: SuiteSummary | null;
    /** task_id -> pair_id (SD-75). Missing on an API without SD-75. */
    pairs?: Record<string, string>;
}

/** Every persisted suite run, newest first. Suites are shared across users. */
export function useSuites() {
    return useQuery({
        queryKey: ["suites"],
        queryFn: () => api<Suite[]>("/suites"),
    });
}

/** GET /suites/{id}, re-checked every 5 seconds while the suite is still running. */
export function useSuite(suiteId: number | null) {
    return useQuery({
        queryKey: ["suite", suiteId],
        queryFn: () => api<SuiteDetail>(`/suites/${suiteId}`),
        enabled: suiteId !== null,
        refetchInterval: (query) =>
            query.state.data?.status === "running" && !query.state.error
                ? 5000
                : false,
    });
}
