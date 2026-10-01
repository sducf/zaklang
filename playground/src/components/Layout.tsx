import { NavLink, Outlet } from "react-router";

const links = [
    { to: "/playground", label: "Playground" },
    { to: "/explorer", label: "Explorer" },
    { to: "/login", label: "Login" },
];

function Layout() {
    return (
        <div className="min-h-screen">
            <header className="flex items-center gap-6 border-b px-6 py-3">
                <span className="font-semibold">ZakLang</span>
                <nav className="flex gap-4">
                    {links.map((link) => (
                        <NavLink
                            key={link.to}
                            to={link.to}
                            className={({ isActive }) =>
                                isActive ? "underline" : undefined
                            }
                        >
                            {link.label}
                        </NavLink>
                    ))}
                </nav>
            </header>
            <main className="p-6">
                <Outlet />
            </main>
        </div>
    );
}

export default Layout;
