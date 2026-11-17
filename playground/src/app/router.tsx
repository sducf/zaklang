import { createBrowserRouter, Navigate } from "react-router";
import Layout from "@/components/Layout.tsx";
import RequireAuth from "@/components/RequireAuth.tsx";
import ExplorerPage from "@/pages/ExplorerPage.tsx";
import PairPage from "@/pages/PairPage.tsx";
import SuitePage, { ExplorerLanding } from "@/pages/SuitePage.tsx";
import LoginPage from "@/pages/LoginPage.tsx";
import PlaygroundPage from "@/pages/PlaygroundPage.tsx";
import DocsPage from "@/pages/DocsPage.tsx";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Navigate to="/playground" replace /> },
            {
                element: <RequireAuth />,
                children: [
                    { path: "playground", element: <PlaygroundPage /> },
                    {
                        path: "explorer",
                        children: [
                            { index: true, element: <ExplorerLanding /> },
                            { path: "runs", element: <ExplorerPage /> },
                            { path: "pairs/:pairId", element: <PairPage /> },
                            { path: "suites", element: <SuitePage /> },
                            { path: "suites/:suiteId", element: <SuitePage /> },
                        ],
                    },
                ],
            },
            { path: "login", element: <LoginPage /> },
            { path: "docs", element: <DocsPage /> },
            { path: "*", element: <Navigate to="/playground" replace /> },
        ],
    },
]);
