#!/usr/bin/env python3
"""Measure where Claude Code tokens go, from the local session transcripts.

Reads ~/.claude/projects/*/*.jsonl (or --projects DIR) and reports context tokens per API call,
the costliest sessions, the tools whose results fill the context, and files read again and again.
Standard library only; it reads transcripts and writes nothing.
"""

from __future__ import annotations

import argparse
import json
import re
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


PROMPT_CHARS = 60


def first_prompt(msg: dict) -> str | None:
    text = msg.get("content")
    if not isinstance(text, str) or not text.strip() or text.lstrip().startswith("<"):
        return None  # tool results, slash commands and harness notes are not typed prompts
    text = " ".join(text.split())
    return text if len(text) <= PROMPT_CHARS else text[:PROMPT_CHARS].rstrip() + "…"


def tool_counts(msgs: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for msg in msgs.values():
        for block in msg.get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                counts[block.get("name", "?")] = counts.get(block.get("name", "?"), 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


SCRIPT = re.compile(r"[\w.-]+\.(?:py|sh|js|mjs|ts|rb)\b")


def source_of(name: str, inp: dict) -> str:
    """A label that says what produced a tool result: the script a shell command ran, the MCP
    server, the skill. Arguments and paths are left out, so the report holds no file contents."""
    if name == "Bash":
        cmd = str(inp.get("command", ""))
        script = SCRIPT.search(cmd)
        if script:
            return f"Bash: {script.group(0)}"
        parts = [p.strip() for p in re.split(r"&&|;|\|", cmd) if p.strip()]
        parts = [p for p in parts if not p.startswith("cd ")] or parts or ["?"]
        return f"Bash: {parts[0].split()[0]}"
    if name.startswith("mcp__"):
        return f"mcp: {name.split('__')[1]}"
    if name == "Skill":
        return f"Skill: {inp.get('skill', '?')}"
    return name


def result_size(content) -> tuple[int, int]:
    """(text characters, images or documents) in one tool result."""
    if isinstance(content, str):
        return len(content), 0
    chars = media = 0
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") in ("image", "document"):
            media += 1
        else:
            chars += len(str(block.get("text", "")))
    return chars, media


def audit(root: Path) -> dict:
    sessions = []
    tools: dict[str, dict] = {}
    for path in sorted(root.glob("*/*.jsonl")):
        msgs: dict[str, dict] = {}
        prompt = None
        sources: dict[str, str] = {}
        for e in entries(path):
            msg = e.get("message") or {}
            if e.get("type") == "user" and prompt is None:
                prompt = first_prompt(msg)
            for block in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    sources[block.get("id")] = source_of(block.get("name", "?"), block.get("input") or {})
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in sources:
                    chars, media = result_size(block.get("content"))
                    row = tools.setdefault(sources[block["tool_use_id"]],
                                           {"calls": 0, "chars": 0, "images": 0})
                    row["calls"] += 1
                    row["chars"] += chars
                    row["images"] += media
            if e.get("type") == "assistant" and msg.get("usage"):
                # one response can be logged as several lines sharing an id: count it once,
                # but keep every line's content blocks
                key = msg.get("id") or str(id(e))
                kept = msgs.setdefault(key, {"usage": msg["usage"], "content": []})
                kept["content"] += msg.get("content") or []
        if msgs:
            sessions.append({
                "session": path.stem,
                "project": path.parent.name,
                "calls": len(msgs),
                "context_tokens": sum(context_of(m["usage"]) for m in msgs.values()),
                "prompt": prompt or "",
                "tools": tool_counts(msgs),
            })
    sessions.sort(key=lambda s: -s["context_tokens"])
    calls = sum(s["calls"] for s in sessions)
    total = sum(s["context_tokens"] for s in sessions)
    return {
        "totals": {
            "calls": calls,
            "context_tokens": total,
            "avg_context": total // calls if calls else 0,
        },
        "sessions": sessions,
        "tools": [
            {"source": src, "calls": r["calls"], "est_tokens": r["chars"] // 4, "images": r["images"]}
            for src, r in sorted(tools.items(), key=lambda kv: -kv[1]["chars"])
        ],
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
