"""Tests for verify_red_green.py. Run: python3 test_verify_red_green.py"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("verify_red_green.py")
TEST = 'import app\nassert app.value() == 2, "value should be 2"\n'


class Repo:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def git(self, *args: str) -> str:
        done = subprocess.run(
            ["git", *args], cwd=self.path, capture_output=True, text=True, check=True
        )
        return done.stdout.strip()

    def commit(self, files: dict) -> str:
        for name, body in files.items():
            target = self.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "change")
        return self.git("rev-parse", "HEAD")


def verify(repo: Repo, red: str, green: str, expect: str = "value should be 2", test: str = "tests/test_app.py"):
    cmd = [sys.executable, str(SCRIPT), "--repo", str(repo.path), "--red", red, "--green", green]
    cmd += ["--expect", expect, "--", sys.executable, test]
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": "."}
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


class VerifyRedGreen(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Repo(Path(self.tmp.name))
        self.repo.commit({"app.py": "def value():\n    return 1\n"})

    def test_accepts_a_test_that_failed_first_then_passed(self):
        red = self.repo.commit({"tests/test_app.py": TEST})
        green = self.repo.commit({"app.py": "def value():\n    return 2\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)

    def test_rejects_a_test_committed_with_its_code(self):
        red = self.repo.commit(
            {"tests/test_app.py": TEST, "app.py": "def value():\n    return 2\n"}
        )
        green = self.repo.commit({"README.md": "x\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("non-test", done.stdout)

    def test_rejects_a_test_that_never_failed(self):
        red = self.repo.commit({"tests/test_app.py": "assert True\n"})
        green = self.repo.commit({"app.py": "def value():\n    return 2\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("passed at the red commit", done.stdout)

    def test_rejects_a_failure_for_the_wrong_reason(self):
        red = self.repo.commit({"tests/test_app.py": "import app\nthis is a syntax error\n"})
        green = self.repo.commit({"app.py": "def value():\n    return 2\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("expected reason", done.stdout)

    def test_rejects_a_test_still_failing_at_green(self):
        red = self.repo.commit({"tests/test_app.py": TEST})
        green = self.repo.commit({"app.py": "def value():\n    return 3\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("failed at the green commit", done.stdout)

    def test_rejects_weakening_the_test_to_go_green(self):
        red = self.repo.commit({"tests/test_app.py": TEST})
        green = self.repo.commit({"tests/test_app.py": "assert True\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("changed between", done.stdout)

    def test_rejects_a_green_commit_that_does_not_descend_from_red(self):
        base = self.repo.git("rev-parse", "HEAD")
        red = self.repo.commit({"tests/test_app.py": TEST})
        self.repo.git("checkout", "-q", "-b", "other", base)
        green = self.repo.commit({"app.py": "def value():\n    return 2\n"})
        done = verify(self.repo, red, green)
        self.assertEqual(done.returncode, 1)
        self.assertIn("does not descend", done.stdout)

    def test_leaves_no_worktrees_behind(self):
        red = self.repo.commit({"tests/test_app.py": TEST})
        green = self.repo.commit({"app.py": "def value():\n    return 2\n"})
        verify(self.repo, red, green)
        self.assertEqual(len(self.repo.git("worktree", "list").splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
