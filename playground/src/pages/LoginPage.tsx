import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation } from "react-router";
import Icon from "@/components/Icon";
import { ApiError } from "@/lib/api";
import { login, register, useAuth } from "@/lib/auth";

type Mode = "login" | "register";

const modes: { value: Mode; label: string }[] = [
    { value: "login", label: "Sign in" },
    { value: "register", label: "Create account" },
];

export default function LoginPage() {
    const auth = useAuth();
    const location = useLocation();
    const [mode, setMode] = useState<Mode>("login");
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);

    if (auth.status === "loading") return null;
    if (auth.status === "signed-in") {
        const from = (location.state as { from?: string } | null)?.from;
        return <Navigate to={from ?? "/playground"} replace />;
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError(null);
        setSubmitting(true);
        try {
            await (mode === "login" ? login : register)(email, password);
        } catch (err) {
            setError(
                err instanceof ApiError
                    ? err.message
                    : "Could not reach the server. Try again.",
            );
            setSubmitting(false);
        }
    }

    const submitLabel = modes.find((item) => item.value === mode)?.label;

    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        YOUR WORKSPACE
                    </div>
                    <h1>
                        {mode === "login" ? "Welcome back" : "Join the lab"}
                        <span className="title-dot">.</span>
                    </h1>
                    <p>
                        Sign in to run Zak in the Playground and keep your run
                        history.
                    </p>
                </div>
            </div>
            <section className="workspace-welcome auth-card">
                <span className="welcome-mark">z.</span>
                <div className="segmented-control auth-mode">
                    {modes.map((item) => (
                        <button
                            key={item.value}
                            type="button"
                            className={
                                mode === item.value ? "selected" : undefined
                            }
                            aria-pressed={mode === item.value}
                            onClick={() => {
                                setMode(item.value);
                                setError(null);
                            }}
                        >
                            {item.label}
                        </button>
                    ))}
                </div>
                <form className="auth-form" onSubmit={handleSubmit}>
                    <label className="auth-field">
                        <span className="eyebrow">EMAIL</span>
                        <input
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                        />
                    </label>
                    <label className="auth-field">
                        <span className="eyebrow">PASSWORD</span>
                        <input
                            type="password"
                            autoComplete={
                                mode === "login"
                                    ? "current-password"
                                    : "new-password"
                            }
                            required
                            value={password}
                            onChange={(event) =>
                                setPassword(event.target.value)
                            }
                        />
                        {mode === "register" && (
                            <small>At least 8 characters.</small>
                        )}
                    </label>
                    {error && (
                        <p className="auth-error" role="alert">
                            {error}
                        </p>
                    )}
                    <button
                        className="button primary"
                        type="submit"
                        disabled={submitting}
                    >
                        {submitLabel} <Icon name="arrow" size={15} />
                    </button>
                </form>
            </section>
        </>
    );
}
