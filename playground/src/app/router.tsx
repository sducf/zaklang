import { createBrowserRouter, Navigate } from "react-router";
import Layout from "@/components/Layout.tsx";
import ExplorerPage from "@/pages/ExplorerPage.tsx";
import LoginPage from "@/pages/LoginPage.tsx";
import PlaygroundPage from "@/pages/PlaygroundPage.tsx";

export const router = createBrowserRouter([
    {
        path: "/",
        element: <Layout />,
        children: [
            { index: true, element: <Navigate to="/playground" replace /> },
            { path: "playground", element: <PlaygroundPage /> },
            { path: "explorer", element: <ExplorerPage /> },
            { path: "login", element: <LoginPage /> },
        ],
    },
]);
