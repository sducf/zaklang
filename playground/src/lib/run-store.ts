import { useSyncExternalStore } from "react";
import type { DemoRun } from "@/lib/demo";

const key = "zaklang-demo-runs-v1";
const listeners = new Set<() => void>();

function readRuns(): DemoRun[] {
    try {
        const value: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
        if (!Array.isArray(value)) return [];
        return value.filter(
            (run): run is DemoRun =>
                run &&
                typeof run.id === "string" &&
                typeof run.taskId === "string" &&
                typeof run.source === "string" &&
                typeof run.python === "string" &&
                typeof run.model === "string" &&
                typeof run.seed === "number" &&
                typeof run.passed === "boolean" &&
                typeof run.promptTokens === "number" &&
                typeof run.completionTokens === "number" &&
                typeof run.createdAt === "string" &&
                (run.language === "zak" || run.language === "python"),
        );
    } catch {
        return [];
    }
}

let runs = readRuns();

function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

export function useDemoRuns() {
    return useSyncExternalStore(subscribe, () => runs);
}

export function saveDemoRun(run: DemoRun) {
    runs = [run, ...runs].slice(0, 50);
    try {
        localStorage.setItem(key, JSON.stringify(runs));
    } catch {
        /* In-memory history works when storage is unavailable. */
    }
    listeners.forEach((listener) => listener());
}

window.addEventListener("storage", (event) => {
    if (event.key === key || event.key === null) {
        runs = readRuns();
        listeners.forEach((listener) => listener());
    }
});
