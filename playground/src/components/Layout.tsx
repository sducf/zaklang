import { Link, NavLink, Outlet, useLocation } from "react-router";
import Icon from "@/components/Icon";
import type { IconName } from "@/components/Icon";

const links: { to: string; label: string; icon: IconName }[] = [
    { to: "/playground", label: "Playground", icon: "terminal" },
    { to: "/explorer", label: "Explorer", icon: "chart" },
    { to: "/docs", label: "Documentation", icon: "book" },
];

function Layout() {
    const location = useLocation();
    const current =
        links.find((link) => location.pathname.startsWith(link.to))?.label ??
        "Workspace";
    return (
        <div className="app-shell">
            <a href="#main-content" className="skip-link">
                Skip to content
            </a>
            <aside className="sidebar">
                <Link to="/playground" className="brand">
                    <span className="brand-mark">
                        z<span>.</span>
                    </span>
                    <span>
                        zaklang<span className="brand-version">v0.1</span>
                    </span>
                </Link>
                <div className="workspace-label">
                    <span className="workspace-avatar">Z</span>
                    <span>
                        Zak workspace<small>Development</small>
                    </span>
                    <span
                        className="workspace-status"
                        title="Prototype workspace"
                    />
                </div>
                <div className="nav-label">WORKSPACE</div>
                <nav className="main-nav" aria-label="Main navigation">
                    {links.map((link) => (
                        <NavLink
                            key={link.to}
                            to={link.to}
                            className={({ isActive }) =>
                                isActive ? "nav-item active" : "nav-item"
                            }
                        >
                            <Icon name={link.icon} />
                            {link.label}
                            {link.to === "/playground" && (
                                <span className="nav-tag">LAB</span>
                            )}
                        </NavLink>
                    ))}
                </nav>
                <div className="sidebar-bottom">
                    <div className="project-note">
                        <span className="eyebrow">
                            LESS SYNTAX. MORE SIGNAL.
                        </span>
                        <p>
                            A small language.
                            <br />A measurable difference.
                        </p>
                        <Link to="/docs">
                            Meet Zak Core <Icon name="arrow" size={14} />
                        </Link>
                    </div>
                    <Link to="/login" className="profile-link">
                        <span className="profile-avatar">D</span>
                        <span>
                            Demo workspace<small>Local prototype</small>
                        </span>
                        <Icon name="chevron" size={15} />
                    </Link>
                </div>
            </aside>
            <div className="main-shell">
                <header className="topbar">
                    <div className="breadcrumb">
                        <span>Workspace</span>
                        <span className="breadcrumb-slash">/</span>
                        <span>{current}</span>
                    </div>
                    <div className="topbar-right">
                        <span className="prototype-badge">
                            <span className="status-dot" />
                            Prototype mode
                        </span>
                        <Link to="/docs" className="topbar-docs">
                            Zak Core v0.1 <Icon name="external" size={13} />
                        </Link>
                    </div>
                </header>
                <main id="main-content" className="main-content">
                    <Outlet />
                </main>
                <footer className="app-footer">
                    <span>
                        <span className="status-dot" /> Demo adapter · no
                        backend connected
                    </span>
                    <span>ZakLang / Senior Design 2026–27</span>
                </footer>
            </div>
        </div>
    );
}

export default Layout;
