import type { CSSProperties } from "react";

export type IconName =
    | "terminal"
    | "chart"
    | "book"
    | "arrow"
    | "play"
    | "check"
    | "copy"
    | "reset"
    | "chevron"
    | "code"
    | "download"
    | "clock"
    | "close"
    | "plus"
    | "external"
    | "cpu";

const paths: Record<IconName, string> = {
    terminal: "m5 7 5 5-5 5m8 0h6M3 3h18v18H3z",
    chart: "M4 4v16h16M8 15v-4m5 4V7m5 8v-6",
    book: "M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1m0-15c3-2 6-2 9-1v15c-3-1-6-1-9 1V5z",
    arrow: "M5 12h14m-5-5 5 5-5 5",
    play: "m8 5 11 7-11 7V5z",
    check: "m5 12 4 4L19 6",
    copy: "M9 9h11v11H9zM15 9V4H4v11h5",
    reset: "M4 10a8 8 0 1 1 1 8M4 4v6h6",
    chevron: "m8 10 4 4 4-4",
    code: "m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16",
    download: "M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5",
    clock: "M12 8v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0",
    close: "m6 6 12 12M6 18 18 6",
    plus: "M12 5v14M5 12h14",
    external: "M14 3h7v7m0-7L10 14M10 3H3v18h18v-7",
    cpu: "M7 7h10v10H7zM10 1v6m4-6v6m-4 10v6m4-6v6M1 10h6m-6 4h6m10-4h6m-6 4h6",
};

export default function Icon({
    name,
    size = 18,
    style,
}: {
    name: IconName;
    size?: number;
    style?: CSSProperties;
}) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            style={style}
        >
            <path d={paths[name]} />
        </svg>
    );
}
