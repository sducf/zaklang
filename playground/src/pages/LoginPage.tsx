import { Link } from "react-router";
import Icon from "@/components/Icon";
import { useDemoRuns } from "@/lib/run-store";

export default function LoginPage() {
    const runs = useDemoRuns();
    return (
        <>
            <div className="page-heading">
                <div>
                    <div className="eyebrow heading-eyebrow">
                        YOUR WORKSPACE
                    </div>
                    <h1>
                        Welcome to the lab<span className="title-dot">.</span>
                    </h1>
                    <p>
                        A place to try Zak, inspect output, and ask better
                        questions.
                    </p>
                </div>
            </div>
            <section className="workspace-welcome">
                <span className="welcome-mark">z.</span>
                <h2>You’re in the demo workspace</h2>
                <p>
                    You can use the Playground without an account. Your last 50
                    demo runs are saved in this browser, ready to inspect in
                    Explorer.
                </p>
                <div className="welcome-stats">
                    <span>
                        <strong>{runs.length}</strong> local demo runs
                    </span>
                    <span>
                        <strong>3</strong> development tasks
                    </span>
                </div>
                <Link className="button primary" to="/playground">
                    Open Playground <Icon name="arrow" size={15} />
                </Link>
                <div className="welcome-note">
                    <Icon name="book" size={15} />
                    Email/password accounts, roles, and quotas will connect to
                    the backend in a later iteration.
                </div>
            </section>
        </>
    );
}
