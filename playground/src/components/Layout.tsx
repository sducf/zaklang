import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import Icon from "@/components/Icon";
import { ZakMark, ZakWordmark } from "@/components/Logo";
import { logout, useAuth } from "@/lib/auth";

const links = [
    { to: "/playground", label: "Playground" },
    { to: "/explorer", label: "Explorer" },
    { to: "/docs", label: "Docs" },
];

function AccountMenu() {
    const auth = useAuth();
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const root = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (!open) return;
        function onPointer(event: PointerEvent) {
            if (!root.current?.contains(event.target as Node)) setOpen(false);
        }
        function onKey(event: KeyboardEvent) {
            if (event.key === "Escape") setOpen(false);
        }
        document.addEventListener("pointerdown", onPointer);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("pointerdown", onPointer);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    if (auth.status !== "signed-in") {
        return (
            <Link to="/login" className="btn btn-ghost ml-auto h-11 px-3">
                Sign in
            </Link>
        );
    }

    const email = auth.user.email;
    return (
        <div ref={root} className="relative ml-auto">
            <button
                type="button"
                className="flex h-11 items-center gap-2 rounded-md pr-2 pl-1.5 text-text-secondary hover:bg-surface-hover hover:text-text-primary max-md:px-1"
                aria-expanded={open}
                aria-controls="account-panel"
                onClick={() => setOpen(!open)}
            >
                <span className="sr-only">Account menu</span>
                <span
                    aria-hidden="true"
                    className="grid size-7 place-items-center rounded-full bg-surface-selected text-xs font-medium text-text-primary"
                >
                    {email.charAt(0).toUpperCase()}
                </span>
                <span className="max-w-48 truncate max-md:hidden">
                    {email}
                </span>
                <Icon name="chevron-down" className="max-md:hidden" />
            </button>
            {open && (
                <div
                    id="account-panel"
                    className="menu absolute top-full right-0 z-20 mt-2 w-64 rounded-lg border border-border-default bg-surface-raised p-1"
                >
                    <div className="px-3 py-2">
                        <div className="truncate text-text-primary">
                            {email}
                        </div>
                        <div className="label">{auth.user.role}</div>
                    </div>
                    <button
                        type="button"
                        className="flex h-11 w-full items-center rounded-md px-3 text-left text-text-primary hover:bg-surface-selected"
                        onClick={() => {
                            setOpen(false);
                            logout();
                            navigate("/login", { replace: true });
                        }}
                    >
                        Sign out
                    </button>
                </div>
            )}
        </div>
    );
}

function Layout() {
    const location = useLocation();

    // Login is a centered card on its own, with no top bar.
    if (location.pathname === "/login") {
        return (
            <main id="main-content">
                <Outlet />
            </main>
        );
    }

    return (
        <div className="min-h-svh">
            <a
                href="#main-content"
                className="sr-only rounded-md bg-surface-raised px-3 py-2 text-text-primary focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50"
            >
                Skip to content
            </a>
            <header className="sticky top-0 z-10 flex h-14 items-center gap-2 border-b border-border-default bg-surface-glass px-8 backdrop-blur-xl max-md:gap-1 max-md:px-4">
                <Link
                    to="/playground"
                    className="flex h-11 items-center gap-2 rounded-md pr-2 text-text-primary hover:text-text-primary max-md:pr-1"
                    aria-label="zaklang"
                >
                    <ZakMark className="size-6" />
                    <ZakWordmark className="h-4 w-[65px] max-md:hidden" />
                </Link>
                <nav
                    className="ml-4 flex items-center gap-1 max-md:ml-1 max-md:gap-0"
                    aria-label="Main navigation"
                >
                    {links.map((link) => (
                        <NavLink
                            key={link.to}
                            to={link.to}
                            className={({ isActive }) =>
                                `relative flex h-11 items-center rounded-md px-3 font-medium no-underline max-md:px-2 ${
                                    isActive
                                        ? "text-text-primary after:absolute after:inset-x-3 after:-bottom-1.5 after:h-0.5 after:rounded-full after:bg-surface-action max-md:after:inset-x-2"
                                        : "text-text-secondary hover:text-text-primary"
                                }`
                            }
                        >
                            {link.label}
                        </NavLink>
                    ))}
                </nav>
                <AccountMenu />
            </header>
            <main
                id="main-content"
                className="mx-auto max-w-[1120px] px-8 pt-10 pb-24 max-md:px-4 max-md:pt-6 max-md:pb-16"
            >
                <Outlet />
            </main>
        </div>
    );
}

export default Layout;
