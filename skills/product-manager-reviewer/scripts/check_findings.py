#!/usr/bin/env python3
"""Keep only product-review findings that quote the document and say how to test the claim.

    check_findings.py --findings F.json --file plan.md

Prints {"accepted": [...], "rejected": [{"finding": ..., "reason": ...}]}, blocking findings
first. A finding must quote its line, name the assumption it questions and the cheapest test of
it, and a `block` must also give a pivot. Exit 0 when every finding is accepted, 1 when any is
rejected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

CLASSES = {"problem", "demand", "alternative", "requirement", "metric", "scope", "market"}
SEVERITIES = ("block", "should-fix", "consider")


class Source:
    """The one document under review."""

    def __init__(self, name, text):
        self.name = name
        self.rows = text.split("\n")

    def problem(self, item):
        if item.get("file") != self.name:
            return "file {} is not the document under review ({})".format(item.get("file"), self.name)
        line, quote = item.get("line"), item.get("quote")
        if not isinstance(line, int) or not isinstance(quote, str) or not quote:
            return "line and quote are required"
        if not 1 <= line <= len(self.rows) or quote not in self.rows[line - 1]:
            return "quote is not on line {} of {}".format(line, self.name)
        return None


def contract_problem(item):
    if not isinstance(item, dict):
        return "a finding must be an object"
    if item.get("class") not in CLASSES:
        return "class must be one of: {}".format(", ".join(sorted(CLASSES)))
    if item.get("severity") not in SEVERITIES:
        return "severity must be one of: {}".format(", ".join(SEVERITIES))
    required = ["assumption", "test"] + (["pivot"] if item["severity"] == "block" else [])
    for key in required:
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            return "{} is required: {}".format(key, {
                "assumption": "say what the document takes for granted",
                "test": "say the cheapest way to find out, naming who to ask or what to measure",
                "pivot": "a blocking finding must say what to build or ask instead"}[key])
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
    parser.add_argument("--file", required=True)
    args = parser.parse_args()
    doc = Path(args.file)
    accepted, rejected = check(json.loads(Path(args.findings).read_text()), Source(doc.name, doc.read_text()))
    print(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
