#!/usr/bin/env python3
"""Prove a test failed before the code that made it pass existed.

    verify_red_green.py --red SHA --green SHA --expect 'REGEX' -- pytest tests/test_x.py

The command runs in a clean checkout of each commit, without a shell. Exit 0 means proven,
1 means rejected (the reason is printed), 2 means bad usage.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_PATH = r"(^|/)(tests?/|test_[^/]*$|[^/]*_test\.[^/]*$|[^/]*\.(test|spec)\.[^/]*$)"
TIMEOUT = 600


class Rejected(Exception):
    pass


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=check)


def changed_files(repo: Path, commit: str) -> list:
    out = git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "-z", "--root", commit).stdout
    return [name for name in out.split("\0") if name]


def run_at(repo: Path, commit: str, command: list) -> subprocess.CompletedProcess:
    """Run ``command`` in a throwaway checkout of ``commit``."""
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        git(repo, "worktree", "add", "-q", "--detach", str(tree), commit)
        try:
            return subprocess.run(
                command, cwd=tree, capture_output=True, text=True, timeout=TIMEOUT
            )
        finally:
            git(repo, "worktree", "remove", "--force", str(tree), check=False)
            git(repo, "worktree", "prune", check=False)


def verify(repo: Path, red: str, green: str, expect: str, command: list, test_path: str) -> None:
    files = changed_files(repo, red)
    tests = [f for f in files if re.search(test_path, f)]
    if not tests:
        raise Rejected("the red commit changes no test files")
    others = sorted(set(files) - set(tests))
    if others:
        raise Rejected(f"the red commit changes non-test files: {', '.join(others)}")
    if git(repo, "merge-base", "--is-ancestor", red, green, check=False).returncode:
        raise Rejected("the green commit does not descend from the red commit")
    if git(repo, "diff", "--quiet", red, green, "--", *tests, check=False).returncode:
        raise Rejected("the tests changed between the red and green commits")

    failed = run_at(repo, red, command)
    if failed.returncode == 0:
        raise Rejected("the test passed at the red commit, so it never failed")
    if not re.search(expect, failed.stdout + failed.stderr):
        tail = (failed.stdout + failed.stderr)[-500:]
        raise Rejected(f"the test failed, but not for the expected reason:\n{tail}")
    passed = run_at(repo, green, command)
    if passed.returncode != 0:
        tail = (passed.stdout + passed.stderr)[-500:]
        raise Rejected(f"the test failed at the green commit:\n{tail}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--red", required=True, help="Commit that adds only the test")
    p.add_argument("--green", required=True, help="Commit where the test passes")
    p.add_argument("--expect", required=True, help="Regex the failure output must match")
    p.add_argument("--test-path", default=TEST_PATH, help="Regex for what counts as a test file")
    p.add_argument("command", nargs="+", help="Test command, after --")
    args = p.parse_args()
    try:
        verify(args.repo, args.red, args.green, args.expect, args.command, args.test_path)
    except Rejected as e:
        print(f"REJECTED: {e}")
        return 1
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print(f"REJECTED: could not run the check: {e}")
        return 1
    print(f"PROVEN: failed at {args.red[:10]} for the expected reason, passed at {args.green[:10]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
