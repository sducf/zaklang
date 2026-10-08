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

export default function CodeEditor({
    value,
    onChange,
    language,
    readOnly = false,
    disabled = false,
    label,
}: {
    value: string;
    onChange?: (value: string) => void;
    language: "zak" | "python";
    readOnly?: boolean;
    disabled?: boolean;
    label: string;
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

    return (
        <div className="code-panel">
            <div className="code-toolbar">
                <span className={`file-icon ${language}`}>
                    {language === "zak" ? "z" : "py"}
                </span>
                <span className="mono">{label}</span>
                <span className="code-label">
                    {readOnly ? "READ ONLY" : "EDITABLE"}
                </span>
                <button
                    className="icon-button"
                    onClick={copy}
                    aria-label={`Copy ${language} code`}
                    title={copied ? "Copied" : "Copy code"}
                    disabled={!value}
                >
                    <Icon name={copied ? "check" : "copy"} size={15} />
                </button>
            </div>
            <div className="editor-body">
                <div
                    className="line-numbers"
                    ref={lineNumbers}
                    aria-hidden="true"
                >
                    {value.split("\n").map((_, i) => (
                        <div key={i}>{i + 1}</div>
                    ))}
                </div>
                {readOnly ? (
                    <pre
                        className="static-code"
                        onScroll={(event) => {
                            if (lineNumbers.current)
                                lineNumbers.current.scrollTop =
                                    event.currentTarget.scrollTop;
                        }}
                    >
                        <code>{highlight(value)}</code>
                    </pre>
                ) : (
                    <div className="editable-code">
                        <pre ref={overlay} aria-hidden="true">
                            <code>
                                {highlight(value)}
                                {"\n"}
                            </code>
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
                        />
                        <span id={instructionId} className="sr-only">
                            Tab inserts two spaces. Shift+Tab leaves the editor.
                        </span>
                    </div>
                )}
            </div>
            <div className="code-footer">
                <span>
                    {copyError
                        ? "Clipboard unavailable. Select code to copy."
                        : `${value.split("\n").length} lines`}
                </span>
                <span>
                    {language === "zak" ? "Zak Core v0.1" : "Python 3.12"}
                    <span className="footer-divider">UTF-8</span>
                </span>
            </div>
        </div>
    );
}
