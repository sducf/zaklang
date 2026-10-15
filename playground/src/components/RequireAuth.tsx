import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "@/lib/auth";

function RequireAuth() {
    const auth = useAuth();
    const location = useLocation();

    // Render nothing while a stored session is being restored.
    if (auth.status === "loading") return null;
    if (auth.status === "signed-out") {
        return (
            <Navigate to="/login" replace state={{ from: location.pathname }} />
        );
    }
    return <Outlet />;
}

export default RequireAuth;
