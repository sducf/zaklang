const API_URL: string = (import.meta.env.VITE_API_URL ?? "").replace(/\/+$/, "");

// The access token lives in memory only. The refresh token is kept in
// localStorage so a reload can restore the session through /auth/refresh.
const refreshKey = "zaklang-refresh-token-v1";
const credentialPaths = new Set(["/auth/login", "/auth/register", "/auth/refresh"]);

export interface TokenPair {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

export class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const expiredListeners = new Set<() => void>();

function readRefreshToken(): string | null {
    try {
        return localStorage.getItem(refreshKey);
    } catch {
        return null;
    }
}

export function hasRefreshToken(): boolean {
    return readRefreshToken() !== null;
}

export function setTokens(tokens: TokenPair | null) {
    accessToken = tokens?.access_token ?? null;
    try {
        if (tokens) localStorage.setItem(refreshKey, tokens.refresh_token);
        else localStorage.removeItem(refreshKey);
    } catch {
        /* Without storage the session lasts until the page reloads. */
    }
}

/** Called when the session cannot be refreshed and the user must sign in again. */
export function onSessionExpired(listener: () => void) {
    expiredListeners.add(listener);
    return () => {
        expiredListeners.delete(listener);
    };
}

function expireSession() {
    setTokens(null);
    expiredListeners.forEach((listener) => listener());
}

async function errorMessage(response: Response): Promise<string> {
    const text = await response.text();
    try {
        // FastAPI sends { detail: string } for HTTPException and
        // { detail: [{ loc, msg }] } for request validation errors.
        const { detail } = JSON.parse(text) as { detail?: unknown };
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) {
            return detail
                .map((item: { loc?: unknown[]; msg?: string }) => {
                    const field = item.loc?.at(-1);
                    return typeof field === "string"
                        ? `${field}: ${item.msg}`
                        : item.msg;
                })
                .join(". ");
        }
    } catch {
        /* Not JSON; fall through to the raw body. */
    }
    return text || response.statusText;
}

function send(path: string, init?: RequestInit): Promise<Response> {
    const headers = new Headers(init?.headers);
    if (init?.body && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
    }
    if (accessToken && !headers.has("Authorization")) {
        headers.set("Authorization", `Bearer ${accessToken}`);
    }
    return fetch(`${API_URL}${path}`, { ...init, headers });
}

/**
 * Trade the stored refresh token for a new token pair. Concurrent callers
 * share one request so a burst of 401s triggers a single refresh.
 */
export function refreshSession(): Promise<boolean> {
    refreshing ??= (async () => {
        const refreshToken = readRefreshToken();
        if (!refreshToken) return false;
        const response = await send("/auth/refresh", {
            method: "POST",
            body: JSON.stringify({ refresh_token: refreshToken }),
        });
        if (!response.ok) return false;
        setTokens((await response.json()) as TokenPair);
        return true;
    })()
        .catch(() => false)
        .finally(() => {
            refreshing = null;
        });
    return refreshing;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
    let response = await send(path, init);

    // These routes report their own 401s (for example a wrong password).
    if (response.status === 401 && !credentialPaths.has(path)) {
        if (await refreshSession()) {
            response = await send(path, init);
        }
        if (response.status === 401) {
            expireSession();
        }
    }

    if (!response.ok) {
        throw new ApiError(response.status, await errorMessage(response));
    }
    if (response.status === 204) {
        return undefined as T;
    }
    return (await response.json()) as T;
}
