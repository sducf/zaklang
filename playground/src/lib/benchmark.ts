import { useQuery } from "@tanstack/react-query";
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
    task_id: string;
    language: Language;
    model_name: string;
    temperature: number | null;
    started_at: string;
    completed_at: string | null;
    status: RunStatus;
    attempts_used: number;
    prompt_tokens_total: number;
    completion_tokens_total: number;
    total_tokens: number;
    latency_ms_total: number;
    attempts: Attempt[];
}

export interface RunListItem {
    id: number;
    task_id: string;
    language: Language;
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

/** Poll a run every second until it reaches a terminal status. */
export function useRun(runId: number | null) {
    return useQuery({
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

export function useRuns() {
    return useQuery({
        queryKey: ["runs"],
        queryFn: () => api<RunListItem[]>("/runs"),
    });
}
