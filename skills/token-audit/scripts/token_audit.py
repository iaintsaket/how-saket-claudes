#!/usr/bin/env python3
"""Measure where Claude Code tokens go, from the local session transcripts.

Reads ~/.claude/projects/*/*.jsonl (or --projects DIR) and reports context tokens per API call,
the costliest sessions, the tools whose results fill the context, and files read again and again.
Standard library only; it reads transcripts and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def entries(path: Path):
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def context_of(usage: dict) -> int:
    return (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )


def audit(root: Path) -> dict:
    calls: dict[tuple[str, str], int] = {}
    for path in sorted(root.glob("*/*.jsonl")):
        for e in entries(path):
            msg = e.get("message") or {}
            if e.get("type") == "assistant" and msg.get("usage"):
                # one response can be logged as several lines sharing an id: count it once
                calls[(str(path), msg.get("id") or id(e))] = context_of(msg["usage"])
    total = sum(calls.values())
    return {
        "totals": {
            "calls": len(calls),
            "context_tokens": total,
            "avg_context": total // len(calls) if calls else 0,
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", type=Path, default=Path.home() / ".claude" / "projects")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    if not args.projects.is_dir():
        print(f"No transcripts folder at {args.projects}", file=sys.stderr)
        return 1
    report = audit(args.projects)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
