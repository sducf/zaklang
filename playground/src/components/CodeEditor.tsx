import { useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent } from "react";
import Icon from "@/components/Icon";

function highlight(code: string) {
    const tokens = code.split(
        /("[^"\n]*"|\b(?:def|return|for|in|if|else|int|str|bool|list|dict|True|False)\b|\b\d+\b|[@^~?#]|\b[IRBSTF]\b)/g,
    );
    return tokens.map((token, index) => {
        const kind = token.startsWith('"')
            ? "string"
            : /^\d+$/.test(token)
              ? "number"
              : /^(def|return|for|in|if|else|[@^~?#])$/.test(token)
                ? "keyword"
                : /^(int|str|bool|list|dict|True|False|[IRBSTF])$/.test(token)
                  ? "type"
                  : "";
        return (
            <span className={kind ? `syntax-${kind}` : undefined} key={index}>
                {token}
            </span>
        );
    });
}

// Shared by the textarea and its highlighted overlay so the two line up exactly.
const codeLayer =
    "absolute inset-0 m-0 h-full w-full overflow-auto border-0 pr-4 text-sm leading-5 whitespace-pre [tab-size:2]";

export default function CodeEditor({
    value,
    onChange,
    language,
    readOnly = false,
    disabled = false,
    label,
    status,
    placeholder,
}: {
    value: string;
    onChange?: (value: string) => void;
    language: "zak" | "python";
    readOnly?: boolean;
    disabled?: boolean;
    label: string;
    status?: string;
    placeholder?: string;
}) {
    const [copied, setCopied] = useState(false);
    const [copyError, setCopyError] = useState(false);
    const copyTimer = useRef<ReturnType<typeof setTimeout> | undefined>(
        undefined,
    );
    const lineNumbers = useRef<HTMLDivElement>(null);
    const overlay = useRef<HTMLPreElement>(null);
    const instructionId = useId();

    useEffect(() => () => clearTimeout(copyTimer.current), []);

    async function copy() {
        try {
            await navigator.clipboard.writeText(value);
            setCopied(true);
            setCopyError(false);
            clearTimeout(copyTimer.current);
            copyTimer.current = setTimeout(() => setCopied(false), 1600);
        } catch {
            setCopyError(true);
        }
    }

    function handleTab(event: KeyboardEvent<HTMLTextAreaElement>) {
        if (event.key !== "Tab" || event.shiftKey || !onChange) return;
        event.preventDefault();
        const target = event.currentTarget;
        const start = target.selectionStart;
        onChange(
            value.slice(0, start) + "  " + value.slice(target.selectionEnd),
        );
        requestAnimationFrame(() => {
            target.selectionStart = target.selectionEnd = start + 2;
        });
    }

    const lines = Math.max(value.split("\n").length, 1);

    return (
        <div className="min-w-0 overflow-hidden rounded-md border border-border-default bg-surface-page">
            <div className="flex h-11 items-center gap-2 border-b border-border-default pr-0.5 pl-3">
                <span className="label text-text-primary">{label}</span>
                <span className="label ml-auto truncate" aria-live="polite">
                    {copyError
                        ? "Clipboard unavailable. Select code to copy."
                        : status}
                </span>
                <button
                    type="button"
                    className="btn btn-ghost btn-icon"
                    onClick={copy}
                    aria-label={`Copy ${language} code`}
                    title={copied ? "Copied" : "Copy code"}
                    disabled={!value}
                >
                    <Icon name={copied ? "check" : "copy"} />
                </button>
            </div>
            <div className="relative flex h-64 py-3 font-mono text-sm leading-5 max-md:h-48">
                <div
                    className="w-10 shrink-0 overflow-hidden pr-3 text-right text-code-gutter select-none"
                    ref={lineNumbers}
                    aria-hidden="true"
                >
                    {Array.from({ length: lines }, (_, i) => (
                        <div key={i}>{i + 1}</div>
                    ))}
                </div>
                {readOnly ? (
                    <pre
                        className="m-0 min-w-0 flex-1 overflow-auto pr-4 text-code-text"
                        onScroll={(event) => {
                            if (lineNumbers.current)
                                lineNumbers.current.scrollTop =
                                    event.currentTarget.scrollTop;
                        }}
                    >
                        {value ? (
                            <code>{highlight(value)}</code>
                        ) : (
                            <span className="font-sans whitespace-normal text-text-tertiary">
                                {placeholder}
                            </span>
                        )}
                    </pre>
                ) : (
                    <div className="relative min-w-0 flex-1">
                        <pre
                            ref={overlay}
                            aria-hidden="true"
                            className={`${codeLayer} pointer-events-none text-code-text [scrollbar-width:none]`}
                        >
                            {value ? (
                                <code>
                                    {highlight(value)}
                                    {"\n"}
                                </code>
                            ) : (
                                <span className="font-sans whitespace-normal text-text-tertiary">
                                    {placeholder}
                                </span>
                            )}
                        </pre>
                        <textarea
                            aria-label={`${language === "zak" ? "Zak" : "Python"} source code`}
                            aria-describedby={instructionId}
                            spellCheck={false}
                            autoCapitalize="off"
                            autoComplete="off"
                            value={value}
                            disabled={disabled}
                            onChange={(event) => onChange?.(event.target.value)}
                            onKeyDown={handleTab}
                            onScroll={(event) => {
                                if (overlay.current) {
                                    overlay.current.scrollTop =
                                        event.currentTarget.scrollTop;
                                    overlay.current.scrollLeft =
                                        event.currentTarget.scrollLeft;
                                }
                                if (lineNumbers.current)
                                    lineNumbers.current.scrollTop =
                                        event.currentTarget.scrollTop;
                            }}
                            className={`${codeLayer} resize-none bg-transparent text-transparent caret-text-action [-webkit-text-fill-color:transparent] focus-visible:outline-offset-[-2px] disabled:cursor-not-allowed`}
                        />
                        <span id={instructionId} className="sr-only">
                            Tab inserts two spaces. Shift+Tab leaves the editor.
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
}
