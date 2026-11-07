#!/usr/bin/env python3
"""Keep only reviewer findings that cite a real line and say what breaks.

    check_findings.py --findings F.json --diff CHANGE.diff --root CHECKOUT
    check_findings.py --findings F.json --file plan.md

Prints {"accepted": [...], "rejected": [{"finding": ..., "reason": ...}]}, blocking findings
first. Exit 0 when every finding is accepted, 1 when any is rejected.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CLASSES = {"wrong-problem", "design", "risk", "tests", "scope", "complexity"}
SEVERITIES = ("block", "should-fix", "consider")
REQUIRED_TEXT = ("scenario", "change")


def added_lines(diff):
    """Map each file to the line numbers a unified diff adds to it."""
    added, path, current, in_hunk = {}, None, 0, False
    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            path, in_hunk = None, False
        elif line.startswith("+++ ") and not in_hunk:
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            current = int(re.search(r"\+(\d+)", line).group(1))
            in_hunk = True
        elif in_hunk and path and line.startswith("+"):
            added.setdefault(path, set()).add(current)
            current += 1
        elif in_hunk and line.startswith(" "):
            current += 1
    return added


class Source:
    """What a finding may cite: the lines a diff adds, or any line of one file."""

    def __init__(self, texts, allowed):
        self.texts = texts
        self.allowed = allowed  # file -> set of citable lines, or None for every line

    @classmethod
    def from_diff(cls, diff, texts):
        return cls(texts, added_lines(diff))

    @classmethod
    def from_file(cls, name, text):
        return cls({name: text}, {name: None})

    def problem(self, item):
        name, line, quote = item.get("file"), item.get("line"), item.get("quote")
        if name not in self.texts or name not in self.allowed:
            return "file {} is not part of this review".format(name)
        if not isinstance(line, int) or not isinstance(quote, str) or not quote:
            return "line and quote are required"
        rows = self.texts[name].split("\n")
        if not 1 <= line <= len(rows) or quote not in rows[line - 1]:
            return "quote is not on line {} of {}".format(line, name)
        limit = self.allowed[name]
        if limit is not None and line not in limit:
            return "line {} of {} was not added by this change".format(line, name)
        return None


def contract_problem(item):
    if not isinstance(item, dict):
        return "a finding must be an object"
    if item.get("class") not in CLASSES:
        return "class must be one of: {}".format(", ".join(sorted(CLASSES)))
    if item.get("severity") not in SEVERITIES:
        return "severity must be one of: {}".format(", ".join(SEVERITIES))
    for key in REQUIRED_TEXT:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            return "{} is required: say what breaks, and what to change".format(key)
    return None


def check(findings, source):
    accepted, rejected = [], []
    for item in findings:
        reason = contract_problem(item) or source.problem(item)
        if reason:
            rejected.append({"finding": item, "reason": reason})
        else:
            accepted.append(item)
    accepted.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return accepted, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--findings", required=True)
    parser.add_argument("--diff")
    parser.add_argument("--root", default=".")
    parser.add_argument("--file")
    args = parser.parse_args()
    if bool(args.diff) == bool(args.file):
        parser.error("pass exactly one of --diff or --file")

    findings = json.loads(Path(args.findings).read_text())
    if args.file:
        source = Source.from_file(Path(args.file).name, Path(args.file).read_text())
    else:
        diff = Path(args.diff).read_text()
        texts = {}
        for name in added_lines(diff):
            target = Path(args.root) / name
            if target.is_file():
                texts[name] = target.read_text(errors="replace")
        source = Source.from_diff(diff, texts)
    accepted, rejected = check(findings, source)
    print(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
