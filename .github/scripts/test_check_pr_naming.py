"""Tests for check_pr_naming.py. Run: python3 -m unittest discover -s .github/scripts"""

import contextlib
import io
import os
import subprocess
import tempfile
import unittest

from check_pr_naming import branch_issue, check_subject, main

GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


class BranchNameTest(unittest.TestCase):
    def test_valid(self):
        for branch, issue in [("SD-1", "1"), ("SD-123", "123"), ("SD-4567", "4567"), ("SD-123-fix", "123"),
                              ("SD-33-zak-core-spec-v0.1", "33"), ("SD-12/login", "12"), ("SD-12a", "12")]:
            self.assertEqual(branch_issue(branch), issue, branch)

    def test_invalid(self):
        for branch in ["feature/SD-123", "SD123", "sd-123", "SD-abc", "feature/login",
                       "SD-", " SD-123", "SD_123", "SD-١٢٣", "main"]:
            self.assertIsNone(branch_issue(branch), repr(branch))


class CommitSubjectTest(unittest.TestCase):
    def test_valid(self):
        for subject in ["SD-123: Fix authentication bug", "SD-123: Add user validation",
                        "SD-123: Update API response handling", "SD-123: Refactor database connection logic",
                        "SD-123: fix: lower case and colons are fine", "SD-123: Fix"]:
            self.assertIsNone(check_subject(subject, "123"), subject)

    def test_wrong_format(self):
        for subject in ["Fixed bug", "sd-123: Fix login", "SD-123 Fix login", "SD123: Fix login",
                        " SD-123: Fix login", "feat(SD-123): Fix login", ""]:
            self.assertIn("must start with", check_subject(subject, "123"), repr(subject))

    def test_missing_description(self):
        for subject in ["SD-123", "SD-123:", "SD-123: ", "SD-123:    ", "SD-123: ab", "SD-123:\t"]:
            self.assertIsNotNone(check_subject(subject, "123"), repr(subject))
        self.assertIn("at least 3", check_subject("SD-123: ab", "123"))

    def test_mismatched_issue(self):
        self.assertIn("SD-456, but the branch is SD-123", check_subject("SD-456: Fix login", "123"))
        self.assertIn("SD-12, but the branch is SD-123", check_subject("SD-12: Fix login", "123"))

    def test_unexpected_whitespace(self):
        for subject in ["SD-123:Fix login", "SD-123:  Fix login", "SD-123:\tFix login"]:
            self.assertIn("exactly one space", check_subject(subject, "123"), repr(subject))


class PullRequestTest(unittest.TestCase):
    """Run main() against real git repositories, including a pull request from a fork."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.upstream = os.path.join(self.tmp.name, "upstream")
        self.git(self.tmp.name, "init", "-q", "-b", "main", self.upstream)
        self.commit(self.upstream, "Initial commit without an issue number")
        self.base = self.sha(self.upstream, "main")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, repo, *args):
        return subprocess.run(["git", "-C", repo, *args], env=GIT_ENV, check=True,
                              capture_output=True, text=True).stdout.strip()

    def commit(self, repo, message):
        self.git(repo, "commit", "-q", "--allow-empty", "-m", message)

    def sha(self, repo, ref="HEAD"):
        return self.git(repo, "rev-parse", ref)

    def run_main(self, branch, base, head):
        out = io.StringIO()
        cwd = os.getcwd()
        os.chdir(self.upstream)
        try:
            with contextlib.redirect_stdout(out):
                code = main(["check_pr_naming.py", branch, base, head])
        finally:
            os.chdir(cwd)
        return code, out.getvalue()

    def test_multiple_valid_commits(self):
        self.git(self.upstream, "checkout", "-q", "-b", "SD-123")
        for message in ["SD-123: Add user validation", "SD-123: Fix authentication bug\n\nLonger body."]:
            self.commit(self.upstream, message)
        code, out = self.run_main("SD-123", self.base, self.sha(self.upstream))
        self.assertEqual(code, 0, out)
        self.assertIn("Checked 2 commit(s), found 0 error(s)", out)

    def test_every_commit_is_checked(self):
        self.git(self.upstream, "checkout", "-q", "-b", "SD-123")
        for message in ["Fixed bug", "SD-123: Add user validation", "SD-456: Fix login", "SD-123: Last"]:
            self.commit(self.upstream, message)
        code, out = self.run_main("SD-123", self.base, self.sha(self.upstream))
        self.assertEqual(code, 1)
        self.assertEqual(out.count("::error::"), 2, out)
        self.assertIn("'Fixed bug'", out)
        self.assertIn("'SD-456: Fix login'", out)

    def test_invalid_branch_fails_before_commits(self):
        self.git(self.upstream, "checkout", "-q", "-b", "feature/login")
        self.commit(self.upstream, "SD-123: Add login")
        code, out = self.run_main("feature/login", self.base, self.sha(self.upstream))
        self.assertEqual(code, 1)
        self.assertIn("Branch 'feature/login' does not start with 'SD-<issue number>'", out)
        self.assertIn("such as 'SD-123'", out)

    def test_invalid_branch_suggests_its_issue_number(self):
        code, out = self.run_main("feature/sd-33-spec", self.base, self.base)
        self.assertEqual(code, 1)
        self.assertIn("such as 'SD-33' or 'SD-33-short-description'", out)

    def test_branch_with_description_uses_its_issue_number(self):
        self.git(self.upstream, "checkout", "-q", "-b", "SD-33-zak-core-spec-v0.1")
        self.commit(self.upstream, "SD-33: Add Zak Core v0.1 specification")
        self.commit(self.upstream, "SD-34: Wrong issue")
        code, out = self.run_main("SD-33-zak-core-spec-v0.1", self.base, self.sha(self.upstream))
        self.assertEqual(code, 1)
        self.assertIn("Checked 2 commit(s), found 1 error(s)", out)
        self.assertIn("SD-34, but the branch is SD-33", out)

    def test_merge_from_main_is_skipped(self):
        self.git(self.upstream, "checkout", "-q", "-b", "SD-123")
        self.commit(self.upstream, "SD-123: Add user validation")
        self.git(self.upstream, "checkout", "-q", "main")
        self.commit(self.upstream, "Unrelated commit that is already on main")
        base = self.sha(self.upstream, "main")
        self.git(self.upstream, "checkout", "-q", "SD-123")
        self.git(self.upstream, "merge", "-q", "--no-ff", "--no-edit", "main")
        code, out = self.run_main("SD-123", base, self.sha(self.upstream))
        self.assertEqual(code, 0, out)
        self.assertIn("Checked 1 commit(s)", out)

    def test_pull_request_from_fork(self):
        fork = os.path.join(self.tmp.name, "fork")
        self.git(self.tmp.name, "clone", "-q", self.upstream, fork)
        self.git(fork, "checkout", "-q", "-b", "SD-7")
        self.commit(fork, "SD-7: Add fork change")
        self.commit(fork, "SD-8: Wrong issue")
        # GitHub exposes a fork's commits in the base repository as refs/pull/<n>/head.
        self.git(self.upstream, "fetch", "-q", fork, "SD-7:refs/pull/1/head")
        code, out = self.run_main("SD-7", self.base, self.sha(self.upstream, "refs/pull/1/head"))
        self.assertEqual(code, 1)
        self.assertIn("Checked 2 commit(s), found 1 error(s)", out)
        self.assertIn("SD-8, but the branch is SD-7", out)

    def test_missing_commit_fails_clearly(self):
        code, out = self.run_main("SD-1", self.base, "0" * 40)
        self.assertEqual(code, 1)
        self.assertIn("Cannot read the commits", out)

    def test_annotation_escapes_commit_text(self):
        self.git(self.upstream, "checkout", "-q", "-b", "SD-1")
        self.commit(self.upstream, "100% done")
        _, out = self.run_main("SD-1", self.base, self.sha(self.upstream))
        self.assertIn("'100%25 done'", out)


if __name__ == "__main__":
    unittest.main()
