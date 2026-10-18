#!/usr/bin/env python3
"""Verify a GitHub repo meets the repo-bootstrap baseline.

Usage: verify_repo.py <owner/repo> [--dir PATH] [--min-coverage N] [--check NAME] [--expect-private]
  --dir            local checkout to scan for the coverage threshold (default: .)
  --min-coverage   minimum line coverage the project must enforce (default: 80)
  --check          required status check / CI job name (default: ci)
  --expect-private the user asked for a private repo; otherwise public is expected
Exits 1 and lists every gap if anything is missing. Needs `gh` logged in.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

REQUIRED_RULES = {"deletion", "non_fast_forward", "pull_request", "required_status_checks"}
# (file glob, regex capturing the threshold as a percent or a 0-1 ratio)
THRESHOLD_PATTERNS = [
    (".github/workflows/*.yml", r"COVERAGE_MIN:\s*[\"']?(\d+(?:\.\d+)?)"),
    (".github/workflows/*.yml", r"--cov-fail-under[= ]\"?(\d+(?:\.\d+)?)"),
    ("pyproject.toml", r"fail_under\s*=\s*(\d+(?:\.\d+)?)"),
    ("setup.cfg", r"fail_under\s*=\s*(\d+(?:\.\d+)?)"),
    (".coveragerc", r"fail_under\s*=\s*(\d+(?:\.\d+)?)"),
    ("jest.config.*", r"lines\s*:\s*(\d+(?:\.\d+)?)"),
    ("package.json", r"\"lines\"\s*:\s*(\d+(?:\.\d+)?)"),
    ("vitest.config.*", r"lines\s*:\s*(\d+(?:\.\d+)?)"),
    ("vite.config.*", r"lines\s*:\s*(\d+(?:\.\d+)?)"),
    ("build.gradle*", r"minimum\s*=\s*\"?(0?\.\d+)"),
    ("pom.xml", r"<minimum>(0?\.\d+)</minimum>"),
]


def gh(*args):
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout) if r.stdout.strip() else None
    except json.JSONDecodeError:
        return r.stdout.strip()


def coverage_thresholds(root: Path):
    found = []
    for glob, rx in THRESHOLD_PATTERNS:
        for f in root.glob(glob):
            for m in re.finditer(rx, f.read_text(encoding="utf-8", errors="ignore")):
                v = float(m.group(1))
                found.append((f.relative_to(root).as_posix(), v * 100 if v <= 1 else v))
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--dir", default=".")
    ap.add_argument("--min-coverage", type=float, default=80)
    ap.add_argument("--check", default="ci")
    ap.add_argument("--expect-private", action="store_true")
    a = ap.parse_args()
    gaps, notes = [], []

    info = gh("repo", "view", a.repo, "--json", "visibility,defaultBranchRef,url")
    if not isinstance(info, dict):
        sys.exit(f"cannot read {a.repo} with gh; is it created and are you logged in?")
    branch = (info.get("defaultBranchRef") or {}).get("name") or "main"
    vis = info["visibility"].lower()
    want = "private" if a.expect_private else "public"
    (notes if vis == want else gaps).append(f"visibility: {vis} (expected {want})")

    rulesets = gh("api", f"repos/{a.repo}/rules/branches/{branch}") or []
    types = {r.get("type") for r in rulesets if isinstance(r, dict)}
    missing = REQUIRED_RULES - types
    if missing:
        gaps.append(f"default branch '{branch}' is missing rules: {sorted(missing)}")
    else:
        notes.append(f"ruleset on '{branch}': {sorted(REQUIRED_RULES)}")
    checks = {c.get("context") for r in rulesets if r.get("type") == "required_status_checks"
              for c in r.get("parameters", {}).get("required_status_checks", [])}
    if a.check not in checks:
        gaps.append(f"required status check '{a.check}' not enforced (have: {sorted(checks) or 'none'})")

    wf = gh("api", f"repos/{a.repo}/contents/.github/workflows?ref={branch}")
    if not wf:
        gaps.append(f"no .github/workflows on '{branch}'")
    else:
        notes.append("workflows: " + ", ".join(w["name"] for w in wf))
        runs = gh("run", "list", "-R", a.repo, "-b", branch, "-L", "1",
                  "--json", "conclusion,status,workflowName,url") or []
        if not runs:
            gaps.append(f"CI has never run on '{branch}'")
        elif runs[0].get("conclusion") != "success":
            gaps.append(f"latest run on '{branch}' is {runs[0].get('status')}/{runs[0].get('conclusion')}: {runs[0].get('url')}")
        else:
            notes.append(f"latest run on '{branch}': success")

    root = Path(a.dir)
    found = coverage_thresholds(root) if root.is_dir() else []
    if not found:
        gaps.append(f"no coverage threshold found in {root.resolve()} (see references/coverage.md)")
    else:
        low = [(f, v) for f, v in found if v < a.min_coverage]
        for f, v in low:
            gaps.append(f"coverage threshold {v:g}% in {f} is below {a.min_coverage:g}%")
        if not low:
            notes.append("coverage thresholds: " + ", ".join(f"{f}={v:g}%" for f, v in found))

    print(f"{a.repo}  {info.get('url')}")
    for n in notes:
        print(f"  ok   {n}")
    for g in gaps:
        print(f"  GAP  {g}")
    print("PASS" if not gaps else f"FAIL ({len(gaps)} gaps)")
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
