import type { CSSProperties } from "react";

export type IconName =
    | "alert"
    | "arrow-right"
    | "check"
    | "chevron-down"
    | "chevron-right"
    | "clock"
    | "code"
    | "copy"
    | "download"
    | "external"
    | "plus"
    | "reset"
    | "spinner"
    | "x";

// Drawn on a 16px grid with a 1.5px stroke.
const paths: Record<IconName, string> = {
    alert: "M8 2.5l6 11H2zM8 6.5v3M8 11.6v.1",
    "arrow-right": "M3 8h10M9 4l4 4-4 4",
    check: "M3.5 8.5l3 3 6-7",
    "chevron-down": "M4 6l4 4 4-4",
    "chevron-right": "M6 4l4 4-4 4",
    clock: "M8 5v3l2 1.5M14 8A6 6 0 1 1 2 8a6 6 0 0 1 12 0",
    code: "M5 4.5L2 8l3 3.5M11 4.5L14 8l-3 3.5",
    copy: "M6 6h7v7H6zM10 6V3H3v7h3",
    download: "M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10",
    external: "M9 3h4v4M13 3 7.5 8.5M12 9.5V13H3V4h3.5",
    plus: "M8 3v10M3 8h10",
    reset: "M3.5 6.5A5 5 0 1 1 4 11M3 3v3.5h3.5",
    spinner: "M8 2a6 6 0 1 1-6 6",
    x: "M4 4l8 8M12 4l-8 8",
};

export default function Icon({
    name,
    size = 16,
    className,
    style,
}: {
    name: IconName;
    size?: number;
    className?: string;
    style?: CSSProperties;
}) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 16 16"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className={className ? `shrink-0 ${className}` : "shrink-0"}
            style={style}
        >
            <path d={paths[name]} />
        </svg>
    );
}
