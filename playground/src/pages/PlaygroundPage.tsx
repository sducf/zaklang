import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router";
import ArtifactDialog from "@/components/ArtifactDialog";
import CodeEditor from "@/components/CodeEditor";
import Icon from "@/components/Icon";
import { matchesReference, model, tasks } from "@/lib/demo";
import type { DemoTask, Language } from "@/lib/demo";
import { saveDemoRun, useDemoRuns } from "@/lib/run-store";

const steps = ["Generate", "Compile", "Transpile", "Run tests"];

function PlaygroundSession({
    task,
    language,
}: {
    task: DemoTask;
    language: Language;
}) {
    const [source, setSource] = useState(task[language]);
    const [stage, setStage] = useState(0);
    const [busy, setBusy] = useState<number | null>(null);
    const [error, setError] = useState("");
    const [seed, setSeed] = useState("42");
    const [outputTab, setOutputTab] = useState("console");
    const [artifact, setArtifact] = useState(false);
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const runs = useDemoRuns();
    const isZak = language === "zak";
    const promptTokens = isZak
        ? task.promptTokens
        : 212 + tasks.indexOf(task) * 18;
    const completionTokens = task.completionTokens[language];
    const validSeed = /^\d+$/.test(seed) && Number(seed) <= 2147483647;

    useEffect(() => () => clearTimeout(timer.current), []);

    function reset() {
        setSource(task[language]);
        setStage(0);
        setError("");
        setOutputTab("console");
    }

    function edit(value: string) {
        setSource(value);
        setStage(0);
        setError("");
    }

    function perform(next: number, all = false) {
        if (busy !== null || !validSeed) return;
        setError("");
        const startingSource = source;
        function advance(current: number) {
            setBusy(current);
            timer.current = setTimeout(() => {
                if (current === 1) setSource(task[language]);
                if (
                    current === 2 &&
                    !matchesReference(startingSource, task, language)
                ) {
                    setError(
                        "DEMO_UNSUPPORTED_SOURCE: This prototype can preview the supplied reference solution only. Reset the editor or select Generate to continue. Edited programs need the compiler API.",
                    );
                    setBusy(null);
                    return;
                }
                const completed =
                    !isZak && (current === 1 || current === 2) ? 3 : current;
                setStage(completed);
                if (current === 4) {
                    saveDemoRun({
                        id: crypto.randomUUID(),
                        taskId: task.id,
                        language,
                        source: startingSource,
                        python: isZak ? task.python : startingSource,
                        seed: Number(seed),
                        model,
                        passed: true,
                        promptTokens,
                        completionTokens,
                        createdAt: new Date().toISOString(),
                    });
                }
                if (all && completed < 4) advance(completed + 1);
                else setBusy(null);
            }, 320);
        }
        advance(next);
    }

    const stageName =
        busy !== null
            ? `${steps[busy - 1]}…`
            : stage === 4
              ? "Demo completed"
              : "Ready when you are";

    return (
        <div
            className="playground-session"
            onKeyDown={(event) => {
                if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.preventDefault();
                    perform(2, true);
                }
            }}
        >
            <section className="task-card" aria-labelledby="task-title">
                <div className="task-heading">
                    <span className="eyebrow">THE TASK</span>
                    <span className="task-category">
                        {task.category}
                        <span className="tag-divider">/</span>Easy
                    </span>
                </div>
                <div className="task-description">
                    <div>
                        <h2 id="task-title">{task.title}</h2>
                        <p>{task.description}</p>
                        <code className="function-signature">
                            {task.signature}
                        </code>
                    </div>
                    <div className="public-examples">
                        <span className="eyebrow">PUBLIC EXAMPLES</span>
                        {task.examples.map((example, i) => (
                            <div className="example" key={i}>
                                <code>{example.input}</code>
                                <Icon name="arrow" size={14} />
                                <code>{example.output}</code>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
            <div className="editor-section-heading">
                <div>
                    <h2>Your workspace</h2>
                    <span>Edit, compile, and inspect the output.</span>
                </div>
                <button
                    className="text-button"
                    onClick={reset}
                    disabled={busy !== null}
                >
                    <Icon name="reset" size={14} />
                    Reset code
                </button>
            </div>
            <section className="editor-workspace" aria-label="Code workspace">
                <div className="editor-topline">
                    <span>
                        <span className="status-dot" />
                        {isZak ? "Zak → Python" : "Python baseline"}
                    </span>
                    <span className="demo-label">
                        REFERENCE SOLUTION · DEMO
                    </span>
                </div>
                <div className="editor-grid">
                    <CodeEditor
                        value={source}
                        onChange={edit}
                        language={language}
                        label={isZak ? "solution.zak" : "solution.py"}
                        disabled={busy !== null}
                    />
                    <div className="output-editor">
                        <CodeEditor
                            value={
                                stage >= 3
                                    ? isZak
                                        ? task.python
                                        : source
                                    : task.python
                            }
                            language="python"
                            readOnly
                            label={
                                stage >= 3
                                    ? isZak
                                        ? "transpiled.py"
                                        : "output.py"
                                    : "reference.py"
                            }
                        />
                        <span
                            className={`preview-tag ${stage >= 3 ? "completed" : ""}`}
                        >
                            {stage >= 3 ? "Demo output" : "Reference preview"}
                        </span>
                    </div>
                </div>
                <div className="pipeline-toolbar">
                    <div
                        className="pipeline-steps"
                        aria-label="Pipeline stages"
                    >
                        {steps.map((step, i) => (
                            <button
                                key={step}
                                aria-label={step}
                                className={`step-button ${stage > i ? "done" : ""} ${busy === i + 1 ? "running" : ""}`}
                                onClick={() => perform(i + 1)}
                                disabled={
                                    busy !== null ||
                                    !validSeed ||
                                    (i > 0 && stage < i) ||
                                    (!isZak && (i === 1 || i === 2))
                                }
                            >
                                <span className="step-number">
                                    {stage > i ? (
                                        <Icon name="check" size={11} />
                                    ) : (
                                        i + 1
                                    )}
                                </span>
                                {!isZak && (i === 1 || i === 2)
                                    ? `${step} · skip`
                                    : step}
                                {i < 3 && (
                                    <Icon
                                        name="chevron"
                                        size={11}
                                        style={{ transform: "rotate(-90deg)" }}
                                    />
                                )}
                            </button>
                        ))}
                    </div>
                    <button
                        className="button primary"
                        onClick={() => perform(2, true)}
                        disabled={busy !== null || !validSeed}
                    >
                        <Icon name="play" size={14} />
                        {busy !== null ? "Running…" : "Run pipeline"}
                        <kbd>⌘ ↵</kbd>
                    </button>
                </div>
            </section>
            <div className="run-options">
                <div className="run-options-fields">
                    <label>
                        Seed
                        <input
                            aria-label="Run seed"
                            inputMode="numeric"
                            type="number"
                            min="0"
                            max="2147483647"
                            step="1"
                            value={seed}
                            disabled={busy !== null}
                            onChange={(event) => {
                                setSeed(event.target.value);
                                setStage(0);
                            }}
                        />
                    </label>
                    <span className="option-separator" />
                    <span>
                        Temperature <code>0.0</code>
                    </span>
                    <span>
                        Max attempts <code>1</code>
                    </span>
                </div>
                <span>
                    <Icon name="cpu" size={13} />
                    {validSeed
                        ? "Deterministic demo fixture"
                        : "Seed must be an integer from 0 to 2147483647"}
                </span>
            </div>
            <section className="results-panel" aria-label="Run output">
                <div className="results-header">
                    <div
                        className="result-tabs"
                        role="tablist"
                        aria-label="Output tabs"
                    >
                        {["console", "results", "history"].map((tab) => (
                            <button
                                role="tab"
                                aria-selected={outputTab === tab}
                                aria-controls="output-tabpanel"
                                id={`tab-${tab}`}
                                key={tab}
                                onClick={() => setOutputTab(tab)}
                                className={outputTab === tab ? "selected" : ""}
                            >
                                {tab === "console" && (
                                    <Icon name="terminal" size={14} />
                                )}
                                {tab.charAt(0).toUpperCase() + tab.slice(1)}
                                {tab === "history" && (
                                    <span className="count-badge">
                                        {runs.length}
                                    </span>
                                )}
                            </button>
                        ))}
                    </div>
                    <span
                        className={`run-state ${stage === 4 ? "success" : ""}`}
                        aria-live="polite"
                    >
                        <span className="status-dot" />
                        {stageName}
                    </span>
                </div>
                <div
                    className="results-body"
                    id="output-tabpanel"
                    role="tabpanel"
                    aria-labelledby={`tab-${outputTab}`}
                    aria-live="polite"
                >
                    {error && (
                        <p className="compiler-error" role="alert">
                            {error}
                        </p>
                    )}
                    {outputTab === "console" && (
                        <div className="console-lines">
                            <div>
                                <span className="console-prefix">›</span>
                                <span>Zak playground initialized.</span>
                                <span className="console-comment">
                                    // local demo adapter
                                </span>
                            </div>
                            {stage >= 1 && (
                                <div>
                                    <span className="console-prefix success">
                                        ✓
                                    </span>
                                    Reference solution loaded.{" "}
                                    <span className="console-comment">
                                        No model request was made.
                                    </span>
                                </div>
                            )}
                            {stage >= 2 && (
                                <div>
                                    <span className="console-prefix success">
                                        ✓
                                    </span>
                                    Source matches the{" "}
                                    {isZak ? "Zak" : "Python"} reference
                                    fixture.
                                </div>
                            )}
                            {stage >= 3 && (
                                <div>
                                    <span className="console-prefix success">
                                        ✓
                                    </span>
                                    Python output loaded from the demo fixture.
                                </div>
                            )}
                            {stage === 4 ? (
                                <div>
                                    <span className="console-prefix success">
                                        ✓
                                    </span>
                                    Demo passed. Saved to local history.{" "}
                                    <span className="console-comment">
                                        No code was executed.
                                    </span>
                                </div>
                            ) : (
                                <div>
                                    <span className="console-prefix muted">
                                        ·
                                    </span>
                                    <span className="muted">
                                        Run the pipeline to explore generation,
                                        transpilation, and results.
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                    {outputTab === "results" &&
                        (stage === 4 ? (
                            <div className="run-metrics">
                                <div>
                                    <span className="eyebrow">OUTCOME</span>
                                    <strong className="success">
                                        Demo passed
                                    </strong>
                                    <small>Reference fixture only</small>
                                </div>
                                <button onClick={() => setArtifact(true)}>
                                    <span className="eyebrow">
                                        TOTAL TOKENS
                                    </span>
                                    <strong>
                                        {(
                                            promptTokens + completionTokens
                                        ).toLocaleString()}{" "}
                                        <Icon name="external" size={13} />
                                    </strong>
                                    <small>
                                        Illustrative prompt + completion
                                    </small>
                                </button>
                                <button onClick={() => setArtifact(true)}>
                                    <span className="eyebrow">COMPLETION</span>
                                    <strong>{completionTokens}</strong>
                                    <small>Illustrative tokens</small>
                                </button>
                                <div>
                                    <span className="eyebrow">ATTEMPTS</span>
                                    <strong>
                                        1 <span className="muted">/ 1</span>
                                    </strong>
                                    <small>No repair attempts</small>
                                </div>
                            </div>
                        ) : (
                            <div className="empty-inline">
                                <Icon name="chart" />
                                <span>
                                    Results will appear after you run the demo
                                    pipeline.
                                </span>
                            </div>
                        ))}
                    {outputTab === "history" &&
                        (runs.length ? (
                            <div className="history-list">
                                {runs.slice(0, 5).map((run) => (
                                    <Link
                                        to={`/explorer?run=${run.id}`}
                                        className="history-row"
                                        key={run.id}
                                    >
                                        <span className="success">
                                            <Icon name="check" size={14} />
                                        </span>
                                        <span>
                                            {
                                                tasks.find(
                                                    (item) =>
                                                        item.id === run.taskId,
                                                )?.title
                                            }
                                        </span>
                                        <code>{run.language}</code>
                                        <span>
                                            {new Date(
                                                run.createdAt,
                                            ).toLocaleTimeString([], {
                                                hour: "2-digit",
                                                minute: "2-digit",
                                            })}
                                        </span>
                                        <Icon name="arrow" size={14} />
                                    </Link>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-inline">
                                <Icon name="clock" />
                                <span>
                                    Your demo runs will be saved here, in this
                                    browser.
                                </span>
                            </div>
                        ))}
                </div>
                <div className="results-footnote">
                    <Icon name="book" size={13} />
                    <span>
                        Prototype runs use sample solutions and illustrative
                        metrics. Hidden tests are never sent to this browser.
                    </span>
                    <Link to="/docs">
                        How it works <Icon name="arrow" size={12} />
                    </Link>
                </div>
            </section>
            {artifact && (
                <ArtifactDialog
                    title="Token accounting · demo fixture"
                    onClose={() => setArtifact(false)}
                >
                    <p>
                        These sample counts are fixtures, not tokenizer
                        measurements. Production runs will store model-native
                        counts and full prompt artifacts for every attempt.
                    </p>
                    <dl className="artifact-facts">
                        <div>
                            <dt>Prompt (including language instructions)</dt>
                            <dd>{promptTokens}</dd>
                        </div>
                        <div>
                            <dt>Completion</dt>
                            <dd>{completionTokens}</dd>
                        </div>
                        <div>
                            <dt>Total across 1 attempt</dt>
                            <dd>{promptTokens + completionTokens}</dd>
                        </div>
                        <div>
                            <dt>Model</dt>
                            <dd>{model}</dd>
                        </div>
                        <div>
                            <dt>Seed / temperature</dt>
                            <dd>{seed} / 0.0</dd>
                        </div>
                    </dl>
                    <pre className="artifact-code">{source}</pre>
                </ArtifactDialog>
            )}
        </div>
    );
}

export default function PlaygroundPage() {
    const [params, setParams] = useSearchParams();
    const task =
        tasks.find((item) => item.id === params.get("task")) ?? tasks[0];
    const language: Language =
        params.get("lang") === "python" ? "python" : "zak";

    function select(taskId: string, lang: Language) {
        setParams({ task: taskId, lang });
    }

    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        THE ZAKLANG LAB
                    </div>
                    <h1>
                        Playground<span className="title-dot">.</span>
                    </h1>
                    <p>
                        From a little Zak to working Python. Explore the
                        pipeline.
                    </p>
                </div>
                <Link to="/explorer" className="button secondary">
                    Open Explorer <Icon name="arrow" size={15} />
                </Link>
            </div>
            <div className="configuration-row">
                <label className="select-field">
                    <span className="eyebrow">01 / TASK</span>
                    <span className="select-wrapper">
                        <Icon name="code" size={16} />
                        <select
                            aria-label="Task"
                            value={task.id}
                            onChange={(event) =>
                                select(event.target.value, language)
                            }
                        >
                            {tasks.map((item) => (
                                <option key={item.id} value={item.id}>
                                    {item.title}
                                </option>
                            ))}
                        </select>
                        <Icon name="chevron" size={14} />
                    </span>
                </label>
                <label className="select-field model-field">
                    <span className="eyebrow">02 / MODEL</span>
                    <span className="select-wrapper">
                        <Icon name="cpu" size={16} />
                        <select aria-label="Model" defaultValue="llama">
                            <option value="llama">{model}</option>
                        </select>
                        <span className="quant-badge">Q4_K_M</span>
                        <Icon name="chevron" size={14} />
                    </span>
                </label>
                <div className="language-field">
                    <span className="eyebrow">03 / LANGUAGE</span>
                    <div className="segmented-control" aria-label="Language">
                        {(["zak", "python"] as const).map((lang) => (
                            <button
                                key={lang}
                                aria-pressed={language === lang}
                                className={language === lang ? "selected" : ""}
                                onClick={() => select(task.id, lang)}
                            >
                                {lang === "zak" ? (
                                    <>
                                        <span className="mini-z">z</span>Zak
                                    </>
                                ) : (
                                    "Python"
                                )}
                            </button>
                        ))}
                    </div>
                </div>
            </div>
            <PlaygroundSession
                key={`${task.id}-${language}`}
                task={task}
                language={language}
            />
        </>
    );
}
