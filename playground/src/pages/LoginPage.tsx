import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation } from "react-router";
import { ZakMark, ZakWordmark } from "@/components/Logo";
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
        <div className="flex min-h-svh flex-col items-center justify-center gap-8 px-4 py-12">
            <div
                className="flex animate-enter items-center gap-3 text-text-primary"
                role="img"
                aria-label="zaklang"
            >
                <ZakMark className="size-10" />
                <ZakWordmark className="h-6 w-[98px]" />
            </div>
            <section
                className="flex w-full max-w-[400px] animate-enter flex-col gap-5 rounded-xl border border-border-default bg-surface-default p-8 [animation-delay:60ms] max-md:px-5 max-md:py-6"
                aria-labelledby="login-title"
            >
                <div>
                    <h1
                        id="login-title"
                        className="text-2xl font-semibold tracking-tight"
                    >
                        {mode === "login" ? "Welcome back" : "Join the lab"}
                    </h1>
                    <p className="mt-1.5 text-text-secondary">
                        Sign in to run Zak in the Playground and keep your run
                        history.
                    </p>
                </div>
                <div
                    className="segmented"
                    role="group"
                    aria-label="Account mode"
                >
                    {modes.map((item) => (
                        <button
                            key={item.value}
                            type="button"
                            className="flex-1"
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
                <form className="flex flex-col gap-4" onSubmit={handleSubmit}>
                    <label className="flex flex-col gap-1.5">
                        <span className="label">Email</span>
                        <input
                            className="field"
                            type="email"
                            autoComplete="email"
                            required
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                        />
                    </label>
                    <label className="flex flex-col gap-1.5">
                        <span className="label">Password</span>
                        <input
                            className="field"
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
                            <small className="text-xs text-text-secondary">
                                At least 8 characters.
                            </small>
                        )}
                    </label>
                    {error && (
                        <p className="text-text-error" role="alert">
                            {error}
                        </p>
                    )}
                    <button
                        className="btn btn-primary w-full"
                        type="submit"
                        disabled={submitting}
                    >
                        {submitLabel}
                    </button>
                </form>
            </section>
        </div>
    );
}
