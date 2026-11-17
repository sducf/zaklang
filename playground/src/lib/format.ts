import { ApiError } from "@/lib/api";
import type { CompilerError, Language } from "@/lib/benchmark";

/** API errors are shown as returned, prefixed with the HTTP status. */
export function errorText(error: unknown) {
    if (error instanceof ApiError) return `HTTP ${error.status}: ${error.message}`;
    return error instanceof Error ? error.message : String(error);
}

export function compilerErrorText(error: CompilerError) {
    return `${error.code} ${error.line}:${error.col} ${error.message}`;
}

export function languageName(language: Language) {
    return language === "zak" ? "Zak" : "Python";
}

export function formatDate(iso: string | null) {
    return iso ? new Date(iso).toLocaleString() : "–";
}

export function formatCount(value: number | null | undefined) {
    return value === null || value === undefined ? "–" : value.toLocaleString();
}

export function formatLatency(ms: number | null) {
    return ms === null ? "–" : `${(ms / 1000).toFixed(2)} s`;
}

/** A share in [0, 1] as a percentage, e.g. 0.6667 -> "66.7%". */
export function formatPercent(value: number | null | undefined) {
    return value === null || value === undefined
        ? "–"
        : `${(value * 100).toFixed(1)}%`;
}

/** A ratio such as Zak / Python tokens, e.g. 0.6667 -> "0.67×". */
export function formatRatio(value: number | null | undefined) {
    return value === null || value === undefined ? "–" : `${value.toFixed(2)}×`;
}

/** A signed difference, always with its sign: "+12", "−412", "0". */
export function formatSigned(value: number, digits = 0) {
    const text = Math.abs(value).toLocaleString(undefined, {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
    });
    if (value > 0) return `+${text}`;
    if (value < 0) return `−${text}`;
    return text;
}

/**
 * Zak minus Python, with the change relative to Python when Python is not zero:
 * "−412 (−38.0%)".
 */
export function formatDelta(zak: number, python: number, digits = 0) {
    const difference = zak - python;
    const signed = formatSigned(difference, digits);
    if (python === 0) return signed;
    const percent = (difference / python) * 100;
    return `${signed} (${formatSigned(percent, 1)}%)`;
}

/** Signed percentage points, for gaps between two rates: "+6.7 pts". */
export function formatPoints(value: number | null | undefined) {
    return value === null || value === undefined
        ? "–"
        : `${formatSigned(value * 100, 1)} pts`;
}
