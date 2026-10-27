import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api";

const queryClient = new QueryClient({
    defaultOptions: {
        queries: {
            // Retry network failures only; an HTTP error is the server's answer.
            retry: (failureCount, error) =>
                !(error instanceof ApiError) && failureCount < 2,
        },
    },
});

function Providers({ children }: { children: ReactNode }) {
    return (
        <QueryClientProvider client={queryClient}>
            {children}
        </QueryClientProvider>
    );
}

export default Providers;
