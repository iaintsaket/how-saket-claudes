#!/usr/bin/env python3
"""Run one fresh, read-only reviewer on a prepared folder and keep findings that hold up.

    run_review.py --dir DIR --out FINDINGS.json

Each run is a new process with no settings, memory, MCP servers, session history or write
tools. A reply that can't be parsed fails the run: it must never count as a clean review.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BRIEF = Path(__file__).resolve().parent.parent / "references" / "reviewer-brief.md"
TOOLS = ["Read", "Grep", "Glob"]
SEVERITIES = {"Critical", "High", "Medium", "Low"}
CONTRACT = ("title", "class", "input", "boundary", "path", "gain", "loss")
KEEP_ENV = ("HOME", "PATH", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "TERM")
TIMEOUT = 1800


def build_cmd(prompt: str, exe: str = "claude") -> list:
    cmd = [exe, "-p", prompt, "--output-format", "json", "--no-session-persistence"]
    cmd += ["--setting-sources", "", "--strict-mcp-config", "--permission-mode", "dontAsk"]
    return cmd + ["--tools", *TOOLS]


def review_env(env: dict) -> dict:
    """Keep what the CLI needs to start and log in, and no tokens from the shell."""
    return {k: env[k] for k in KEEP_ENV if k in env}


def parse_reply(text: str) -> list:
    try:
        findings = json.loads(text[text.index("{") : text.rindex("}") + 1])["findings"]
    except (ValueError, KeyError, TypeError) as e:
        raise ValueError(f"reviewer reply has no findings list: {e}") from e
    if not isinstance(findings, list):
        raise ValueError("reviewer reply: findings is not a list")
    return findings


def problem(finding: dict, code: Path) -> str | None:
    """Why a finding fails the contract, or None. Citing real code is checked, not trusted."""
    missing = [k for k in CONTRACT if not str(finding.get(k) or "").strip()]
    if missing:
        return f"missing {', '.join(missing)}"
    if finding.get("severity") not in SEVERITIES:
        return f"unknown severity {finding.get('severity')!r}"
    target = (code / str(finding.get("file"))).resolve()
    if not target.is_relative_to(code.resolve()) or not target.is_file():
        return f"no such file: {finding.get('file')}"
    line = finding.get("line")
    lines = target.read_bytes().count(b"\n") + 1
    if not isinstance(line, int) or not 1 <= line <= lines:
        return f"line {line} is outside {finding.get('file')}"
    return None


def filter_findings(findings: list, code: Path) -> tuple:
    kept, dropped = [], []
    for f in findings:
        why = problem(f, code) if isinstance(f, dict) else "not an object"
        if why:
            dropped.append({"reason": why, "finding": f})
        else:
            kept.append(f)
    return kept, dropped


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--dir", type=Path, required=True, help="Folder from prepare_review.py")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    exe = shutil.which("claude")
    if not exe:
        print("claude CLI not found", file=sys.stderr)
        return 1
    prompt = BRIEF.read_text(encoding="utf-8")
    done = subprocess.run(
        build_cmd(prompt, exe),
        cwd=args.dir, env=review_env(dict(os.environ)), stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=TIMEOUT,
    )
    try:
        reply = json.loads(done.stdout)
        if reply.get("is_error"):
            raise ValueError(str(reply.get("result"))[:300])
        kept, dropped = filter_findings(parse_reply(str(reply.get("result"))), args.dir / "code")
    except ValueError as e:
        print(f"Review failed, so this round doesn't count: {e}", file=sys.stderr)
        return 1
    args.out.write_text(json.dumps({"findings": kept, "dropped": dropped}, indent=1), encoding="utf-8")
    print(f"{len(kept)} findings kept, {len(dropped)} dropped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
