import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/lib/api";

// One client for the app, so sign-out can clear every cached query.
export const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            // Retry network failures only; an HTTP error is the server's answer.
            retry: (failureCount, error) =>
                !(error instanceof ApiError) && failureCount < 2,
        },
    },
});
