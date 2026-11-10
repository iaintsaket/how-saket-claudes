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
from datetime import date
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
REREAD_AT = 3  # reads of one file in one session before it is flagged


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


def day(text: str) -> str:
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a date: {text!r} (use YYYY-MM-DD)") from None


def audit(root: Path, since: str | None = None) -> dict:
    sessions = []
    rereads: list[dict] = []
    tools: dict[str, dict] = {}
    for path in sorted(root.glob("*/*.jsonl")):
        msgs: dict[str, dict] = {}
        prompt = None
        sources: dict[str, str] = {}
        read_paths: dict[str, str] = {}
        reads: dict[str, list[int]] = {}
        for e in entries(path):
            if since and str(e.get("timestamp", ""))[:10] < since and e.get("timestamp"):
                continue
            msg = e.get("message") or {}
            if e.get("type") == "user" and prompt is None:
                prompt = first_prompt(msg)
            for block in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use":
                    inp = block.get("input") or {}
                    sources[block.get("id")] = source_of(block.get("name", "?"), inp)
                    if block.get("name") == "Read":
                        read_paths[block.get("id")] = str(inp.get("file_path", "?"))
                elif block.get("type") == "tool_result" and block.get("tool_use_id") in sources:
                    chars, media = result_size(block.get("content"))
                    if block["tool_use_id"] in read_paths:
                        seen = reads.setdefault(read_paths[block["tool_use_id"]], [0, 0])
                        seen[0] += 1
                        seen[1] += chars
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
        rereads += [
            {"session": path.stem, "file": f, "reads": n, "est_tokens": chars // 4}
            for f, (n, chars) in reads.items()
            if n >= REREAD_AT
        ]
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
        "rereads": sorted(rereads, key=lambda r: -r["est_tokens"]),
    }


def cap(report: dict, top: int) -> dict:
    return {k: v[:top] if isinstance(v, list) else v for k, v in report.items()}


def as_text(report: dict) -> str:
    t = report["totals"]
    lines = [
        f"{t['calls']:,} API calls, {t['context_tokens']:,} context tokens, "
        f"{t['avg_context']:,} per call on average",
        "",
        "Costliest sessions (context tokens, calls, first prompt, top tools):",
    ]
    for s in report["sessions"]:
        tools = ", ".join(f"{k} {v}" for k, v in list(s["tools"].items())[:4])
        lines.append(f"  {s['context_tokens']:>13,}  {s['calls']:>5}  {s['prompt']}")
        if tools:
            lines.append(f"  {'':>13}  {'':>5}  tools: {tools}")
    lines += ["", "Tool results (estimated tokens = characters / 4; images listed apart):"]
    for r in report["tools"]:
        images = f"  +{r['images']} images" if r["images"] else ""
        lines.append(f"  {r['est_tokens']:>10,}  {r['calls']:>5} calls  {r['source']}{images}")
    if report["rereads"]:
        lines += ["", f"Files read {REREAD_AT}+ times in one session:"]
        for r in report["rereads"]:
            lines.append(f"  {r['est_tokens']:>10,}  x{r['reads']:<3} {r['file']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--projects", type=Path, default=Path.home() / ".claude" / "projects")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--since", type=day, help="count only activity from this date (YYYY-MM-DD)")
    parser.add_argument("--top", type=int, default=10, help="rows per list (default 10)")
    args = parser.parse_args(argv)
    if not args.projects.is_dir():
        print(f"No transcripts folder at {args.projects}", file=sys.stderr)
        return 1
    report = cap(audit(args.projects, args.since), args.top)
    print(json.dumps(report, indent=2) if args.format == "json" else as_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
