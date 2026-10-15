"""Check that a pull request branch and its commits use the SD-<n> issue format.

Usage: python3 check_pr_naming.py <branch> <base-sha> <head-sha>

The script checks the branch name and every non-merge commit in <base-sha>..<head-sha>.
It prints one error for each violation and exits with status 1 if it finds one.
"""

import re
import subprocess
import sys

# Branch names and commit subjects both start with SD-<number>. Any text can follow the number.
# [0-9] and not \d, because \d also matches non-ASCII digits.
BRANCH_RE = re.compile(r"SD-([0-9]+)")


def branch_issue(branch):
    """Return the issue number of a branch or commit subject that starts with SD-<number>, or None."""
    match = BRANCH_RE.match(branch)
    return match[1] if match else None


def check_subject(subject, issue):
    """Return an error for a commit subject on branch SD-<issue>, or None if it is valid."""
    number = branch_issue(subject)
    if number is None:
        return f"the subject must start with 'SD-{issue}'"
    if number != issue:
        return f"the subject uses issue SD-{number}, but the branch is SD-{issue}"
    return None


def pr_commits(base, head):
    """Return (sha, subject) for each non-merge commit in base..head, oldest first."""
    out = subprocess.run(
        ["git", "log", "-z", "--no-merges", "--reverse", "--format=%H%n%B", f"{base}..{head}"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    ).stdout
    commits = []
    for entry in filter(None, out.split("\0")):
        sha, _, message = entry.partition("\n")
        # %s would join a wrapped first paragraph into one line, so read the first line of %B.
        subject = (message.splitlines() or [""])[0].rstrip()
        commits.append((sha, subject))
    return commits


def annotate(message):
    """Print a GitHub Actions error annotation. Escaping stops commit text from adding commands."""
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error::{escaped}")


def main(argv):
    if len(argv) != 4:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    branch, base, head = argv[1:]

    issue = branch_issue(branch)
    if issue is None:
        guess = re.search(r"(?i)SD-?([0-9]+)", branch)
        example = f"SD-{guess[1]}" if guess else "SD-123"
        annotate(
            f"Branch '{branch}' does not start with 'SD-<issue number>'. "
            f"Use a name such as '{example}' or '{example}-short-description'. "
            "Push the commits to that branch and open a new pull request."
        )
        return 1

    try:
        commits = pr_commits(base, head)
    except subprocess.CalledProcessError as error:
        annotate(f"Cannot read the commits in {base}..{head}: {error.stderr.strip()}")
        return 1

    errors = 0
    for sha, subject in commits:
        error = check_subject(subject, issue)
        if error:
            errors += 1
            annotate(f"Commit {sha[:12]} '{subject}': {error}")

    print(f"Branch '{branch}': OK. Checked {len(commits)} commit(s), found {errors} error(s).")
    if errors:
        print(
            f"Fix the commit messages with 'git rebase -i {base[:12]}' and reword each commit, "
            "then push with '--force-with-lease'."
        )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
