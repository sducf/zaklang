"""Make branches, commits and pull requests in the format that the PR naming check requires.

Usage, from anywhere in the repository:
  python .github/scripts/sd.py branch 33          Make branch SD-33 from the current commit and switch to it.
  python .github/scripts/sd.py branch 33 spec     Make branch SD-33-spec instead.
  python .github/scripts/sd.py commit "Add spec"  Commit as 'SD-33: Add spec'. Extra git options go after it, e.g. -a.
  python .github/scripts/sd.py commit             Commit as 'SD-33'. The message after the number is optional.
  python .github/scripts/sd.py pr                 Run the CI check, push the branch and open the pull request.
"""

import re
import shutil
import subprocess
import sys
import webbrowser

from check_pr_naming import BRANCH_RE, branch_issue, check_subject
from check_pr_naming import main as check_pr

BASE = "main"


def git(*args, capture=True):
    result = subprocess.run(["git", *args], capture_output=capture, text=True)
    if result.returncode != 0:
        sys.exit(f"git {' '.join(args)} failed:\n{(result.stderr or '').strip()}")
    return (result.stdout or "").strip()


def current_branch():
    """Return the current branch and its issue number, or stop with the fix to use."""
    branch = git("branch", "--show-current")
    issue = branch_issue(branch)
    if issue is None:
        sys.exit(f"Branch '{branch}' does not start with 'SD-<number>'. "
                 "Run: python .github/scripts/sd.py branch <number>")
    return branch, issue


def cmd_branch(text, name=""):
    number = text.upper().removeprefix("SD-")
    if not BRANCH_RE.fullmatch(f"SD-{number}"):
        sys.exit(f"'{text}' is not an issue number. Use digits only, for example: branch 33")
    branch = f"SD-{number}-{name}" if name else f"SD-{number}"
    git("switch", "-c", branch, capture=False)
    print(f"Now on branch {branch}. Commit with: python .github/scripts/sd.py commit \"<description>\"")


def cmd_commit(*args):
    _, issue = current_branch()
    # A first argument that starts with "-" is a git option, so the commit has no description.
    description, git_args = (args[0].strip(), args[1:]) if args and not args[0].startswith("-") else ("", args)
    # Accept a description that already starts with the prefix, so the prefix is not added twice.
    description = re.sub(rf"^SD-{issue}(?![0-9]):?\s*", "", description)
    subject = f"SD-{issue}: {description}" if description else f"SD-{issue}"
    error = check_subject(subject, issue)
    if error:
        sys.exit(f"'{subject}': {error}")
    git("commit", "-m", subject, *git_args, capture=False)


def cmd_pr():
    branch, _ = current_branch()
    git("fetch", "-q", "origin", BASE)
    print(f"Running the CI naming check against origin/{BASE}...")
    if check_pr(["check_pr_naming.py", branch, f"origin/{BASE}", "HEAD"]) != 0:
        sys.exit("Fix the errors above, then run this command again.")
    git("push", "-u", "origin", branch, capture=False)

    if shutil.which("gh"):
        subprocess.run(["gh", "pr", "create", "--base", BASE, "--fill"])
        return
    remote = git("remote", "get-url", "origin")
    repo = re.sub(r"(\.git)?/?$", "", re.sub(r"^(git@github\.com:|https://github\.com/)", "", remote))
    url = f"https://github.com/{repo}/compare/{BASE}...{branch}?expand=1"
    print(f"Open the pull request here: {url}")
    webbrowser.open(url)


# Each command maps to (function, smallest argument count, largest argument count or None for no limit).
COMMANDS = {"branch": (cmd_branch, 1, 2), "commit": (cmd_commit, 0, None), "pr": (cmd_pr, 0, 0)}

if __name__ == "__main__":
    name, args = (sys.argv[1], sys.argv[2:]) if len(sys.argv) > 1 else ("", [])
    command, least, most = COMMANDS.get(name, (None, 0, 0))
    if command is None or len(args) < least or (most is not None and len(args) > most):
        sys.exit(__doc__.strip())
    command(*args)
