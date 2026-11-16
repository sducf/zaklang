import { useSyncExternalStore } from "react";
import {
    api,
    hasRefreshToken,
    onSessionExpired,
    refreshSession,
    setTokens,
} from "@/lib/api";
import type { TokenPair } from "@/lib/api";
import { queryClient } from "@/lib/queryClient";

export interface User {
    id: string;
    email: string;
    role: string;
    created_at: string;
}

export type AuthState =
    | { status: "loading" }
    | { status: "signed-out" }
    | { status: "signed-in"; user: User };

const listeners = new Set<() => void>();
let state: AuthState = hasRefreshToken()
    ? { status: "loading" }
    : { status: "signed-out" };

function setState(next: AuthState) {
    state = next;
    listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
    listeners.add(listener);
    return () => {
        listeners.delete(listener);
    };
}

export function useAuth() {
    return useSyncExternalStore(subscribe, () => state);
}

async function loadUser() {
    const user = await api<User>("/auth/me");
    setState({ status: "signed-in", user });
}

export async function login(email: string, password: string) {
    const tokens = await api<TokenPair>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
    });
    setTokens(tokens);
    await loadUser();
}

export async function register(email: string, password: string) {
    // Registration returns the new user without tokens, so sign in after it.
    await api<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
    });
    await login(email, password);
}

// Cached runs belong to the user who fetched them, so drop them on sign-out.
function signOut() {
    queryClient.clear();
    setState({ status: "signed-out" });
}

export function logout() {
    setTokens(null);
    signOut();
}

onSessionExpired(signOut);

// Restore a session from the stored refresh token on page load.
if (state.status === "loading") {
    refreshSession()
        .then((ok) => (ok ? loadUser() : logout()))
        .catch(logout);
}
