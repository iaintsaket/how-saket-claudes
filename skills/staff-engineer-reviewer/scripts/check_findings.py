#!/usr/bin/env python3
"""Keep only reviewer findings that cite a real line and say what breaks.

    check_findings.py --findings F.json --diff CHANGE.diff --root CHECKOUT
    check_findings.py --findings F.json --file plan.md

Prints {"accepted": [...], "rejected": [{"finding": ..., "reason": ...}]}, blocking findings
first. A finding may cite any real line of a file in the checkout, because the worst misses are
lines the change should have touched. Each accepted finding says whether the change added its
line, as `in_diff`. Exit 0 when every finding is accepted, 1 when any is rejected.
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
    """What a finding may cite: any real line of a file, marked by whether the change added it."""

    def __init__(self, texts, added, loader=None):
        self.texts = dict(texts)
        self.added = added  # file -> line numbers the change adds, or None when the whole file is under review
        self.loader = loader

    @classmethod
    def from_diff(cls, diff, texts, loader=None):
        return cls(texts, added_lines(diff), loader)

    @classmethod
    def from_file(cls, name, text):
        return cls({name: text}, {name: None})

    def text_of(self, name):
        if name not in self.texts and self.loader and isinstance(name, str):
            self.texts[name] = self.loader(name)
        return self.texts.get(name)

    def problem(self, item):
        name, line, quote = item.get("file"), item.get("line"), item.get("quote")
        text = self.text_of(name)
        if text is None:
            return "file {} is not part of this review".format(name)
        if not isinstance(line, int) or not isinstance(quote, str) or not quote:
            return "line and quote are required"
        rows = text.split("\n")
        if not 1 <= line <= len(rows) or quote not in rows[line - 1]:
            return "quote is not on line {} of {}".format(line, name)
        return None

    def in_diff(self, item):
        lines = self.added.get(item["file"], set())
        return lines is None or item["line"] in lines


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
            accepted.append(dict(item, in_diff=source.in_diff(item)))
    accepted.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return accepted, rejected


def checkout_reader(root):
    """Read a file of the checkout, never one outside it."""
    base = root.resolve()

    def read(name):
        target = (base / name).resolve()
        if base not in target.parents or not target.is_file():
            return None
        return target.read_text(errors="replace")

    return read


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
        source = Source.from_diff(Path(args.diff).read_text(), {}, checkout_reader(Path(args.root)))
    accepted, rejected = check(findings, source)
    print(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
