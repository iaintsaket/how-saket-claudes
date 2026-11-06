#!/usr/bin/env python3
"""Build the only material a blind reviewer sees: the code at the PR's head and its diff.

    prepare_review.py --repo . --pr 12 --out DIR
    prepare_review.py --repo . --base main --head SHA --out DIR

No commit messages, PR text or git history go in. Files are read with `git cat-file`, and the
diff is forced to text, because `export-ignore` and `-diff` in a PR's own .gitattributes could
otherwise hide its changes. Symlinks and submodules are skipped so nothing points outside.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, check=True).stdout


def safe_target(root: Path, name: str) -> Path:
    target = (root / name).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes the review folder: {name}")
    return target


def prepare(repo: Path, base: str, head: str, out: Path) -> dict:
    code = out / "code"
    code.mkdir(mode=0o700, parents=True)
    head_sha = git(repo, "rev-parse", f"{head}^{{commit}}").decode().strip()
    base_sha = git(repo, "merge-base", base, head_sha).decode().strip()
    skipped = []
    for entry in git(repo, "ls-tree", "-r", "-z", head_sha).split(b"\0"):
        if not entry:
            continue
        meta, raw_name = entry.split(b"\t", 1)
        mode, kind, sha = meta.decode().split()
        name = raw_name.decode("utf-8", "surrogateescape")
        if kind != "blob" or mode == "120000":
            skipped.append(name)
            continue
        target = safe_target(code, name)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        target.write_bytes(git(repo, "cat-file", "blob", sha))
    diff = git(repo, "diff", "--text", "--no-ext-diff", "--no-textconv", base_sha, head_sha)
    (out / "change.diff").write_bytes(diff)
    return {"dir": str(out), "base": base_sha, "head": head_sha, "skipped": skipped}


def pr_refs(repo: Path, number: int) -> tuple:
    """Only the two commits: never the PR's title or description."""
    done = subprocess.run(
        ["gh", "pr", "view", str(number), "--json", "baseRefOid,headRefOid"],
        cwd=repo, capture_output=True, text=True, check=True,
    )
    pr = json.loads(done.stdout)
    git(repo, "fetch", "-q", "origin", f"pull/{number}/head")
    return pr["baseRefOid"], pr["headRefOid"]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", type=Path, default=Path("."))
    p.add_argument("--pr", type=int)
    p.add_argument("--base")
    p.add_argument("--head")
    p.add_argument("--out", type=Path, required=True, help="Must not exist yet")
    args = p.parse_args()
    if args.pr:
        base, head = pr_refs(args.repo, args.pr)
    elif args.base and args.head:
        base, head = args.base, args.head
    else:
        p.error("pass --pr, or both --base and --head")
    print(json.dumps(prepare(args.repo, base, head, args.out), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
