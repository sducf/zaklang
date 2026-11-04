import Icon from "@/components/Icon";
import type { RunStatus } from "@/lib/benchmark";

const labels: Record<RunStatus, string> = {
    queued: "Queued",
    running: "Running",
    passed: "Passed",
    failed: "Failed",
    error: "Error",
    timeout: "Timeout",
};

/** Run status as an icon plus a word, never color alone. */
export default function StatusBadge({
    status,
    solid = false,
}: {
    status: RunStatus;
    solid?: boolean;
}) {
    if (status === "passed") {
        return (
            <span className={`badge ${solid ? "badge-solid" : "badge-outline"}`}>
                <Icon name="check" size={14} />
                {labels.passed}
            </span>
        );
    }
    if (status === "queued" || status === "running") {
        return (
            <span className="badge badge-neutral">
                <Icon name="spinner" size={14} className="animate-spin" />
                {labels[status]}
            </span>
        );
    }
    return (
        <span className="badge badge-error">
            <Icon name={status === "timeout" ? "clock" : "alert"} size={14} />
            {labels[status]}
        </span>
    );
}
