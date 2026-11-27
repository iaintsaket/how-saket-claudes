#!/usr/bin/env python3
"""Decide whether a change needs an SEO review, and keep only reviewer findings that hold up.

    git diff BASE...HEAD | seo_review.py scope
    seo_review.py check --findings F.json --root CHECKOUT

`scope` reads a unified diff and prints the changed files that can change how a page is found,
indexed or shared: a page, head or crawl file by its path, or any other file whose added lines
touch titles, descriptions, canonicals, share tags, robots, sitemaps or structured data. It
exits 1 with "no SEO-relevant change" when there are none. `check` prints
{"accepted": [...], "rejected": [{"finding": ..., "reason": ...}]}, worst first, and exits 1
when any finding is rejected.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Files that render a page, its <head>, or what crawlers are told about it.
RELEVANT = [
    r"(^|/)(app|pages|routes|views|templates|layouts)/.+\.(tsx|jsx|ts|js|vue|svelte|astro|mdx?|html?|njk|liquid|erb|hbs)$",
    r"\.(html?|mdx?)$",
    r"(^|/)(robots|sitemap|manifest|_redirects|_headers|redirects)(\.[\w.]+)?$",
    r"(^|/)(seo|head|metadata|meta|site|layout|_document|_app|opengraph-image|twitter-image)\.[\w]+$",
    r"(^|/)(next|nuxt|astro|svelte|gatsby|vite|remix)\.config\.[\w]+$",
]
# Tests, docs about the repo itself and lockfiles never reach a crawler.
IGNORED = [r"\.(test|spec)\.\w+$", r"(^|/)(__tests__|e2e|tests?)/", r"(^|/)(README|CHANGELOG|CONTRIBUTING|SECURITY|LICENSE)(\.md)?$", r"lock"]

# Added lines that set what search engines or share previews read, wherever the file lives.
SEO_TERMS = re.compile(
    r"\b(title|description|canonical|metadata|generateMetadata|noindex|nofollow|robots|sitemap|hreflang|schema\.org|ld\+json)\b"
    r"|og:|twitter:|<h1\b|<head\b|\balt="
)

CLASSES = ("content", "crawl", "intent", "links", "performance", "sharing", "structured-data")
SEVERITIES = ("block", "should-fix", "consider")
REQUIRED_TEXT = ("impact", "change")


def relevant(paths):
    """The paths, in order, that can change how a page is found, indexed or shared."""
    def keep(p):
        return any(re.search(r, p) for r in RELEVANT) and not any(re.search(r, p, re.I) for r in IGNORED)
    return [p for p in paths if p and keep(p)]


def relevant_in_diff(diff):
    """Files a unified diff changes that are SEO-relevant by path or by what their added lines say."""
    files, path = {}, None
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            path = line.split(" b/", 1)[-1]
            files[path] = False
        elif path and line.startswith("+") and not line.startswith("+++") and SEO_TERMS.search(line):
            files[path] = True
    ignored = [p for p in files if any(re.search(r, p, re.I) for r in IGNORED)]
    by_path = set(relevant(list(files)))
    return [p for p in files if p not in ignored and (p in by_path or files[p])]


def problem(item, root):
    if not isinstance(item, dict):
        return "a finding must be an object"
    if item.get("class") not in CLASSES:
        return "class must be one of: {}".format(", ".join(CLASSES))
    if item.get("severity") not in SEVERITIES:
        return "severity must be one of: {}".format(", ".join(SEVERITIES))
    for key in REQUIRED_TEXT:
        if not isinstance(item.get(key), str) or not item[key].strip():
            return "{} is required: say what search or sharing loses, and what to change".format(key)
    name, line, quote = item.get("file"), item.get("line"), item.get("quote")
    base = root.resolve()
    target = (base / str(name)).resolve()
    if base not in target.parents or not target.is_file():
        return "file {} is not in the checkout".format(name)
    if not isinstance(line, int) or not isinstance(quote, str) or not quote:
        return "line and quote are required"
    rows = target.read_text(errors="replace").split("\n")
    if not 1 <= line <= len(rows) or quote not in rows[line - 1]:
        return "quote is not on line {} of {}".format(line, name)
    return None


def check(findings, root):
    """Split findings into accepted (worst first) and rejected with a reason each."""
    accepted, rejected = [], []
    for item in findings:
        reason = problem(item, Path(root))
        if reason:
            rejected.append({"finding": item, "reason": reason})
        else:
            accepted.append(item)
    accepted.sort(key=lambda f: SEVERITIES.index(f["severity"]))
    return accepted, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scope", help="read a unified diff on stdin")
    c = sub.add_parser("check", help="check reviewer findings")
    c.add_argument("--findings", required=True)
    c.add_argument("--root", default=".")
    args = parser.parse_args()

    if args.cmd == "scope":
        paths = relevant_in_diff(sys.stdin.read())
        print("\n".join(paths) if paths else "no SEO-relevant change")
        return 0 if paths else 1
    accepted, rejected = check(json.loads(Path(args.findings).read_text()), args.root)
    print(json.dumps({"accepted": accepted, "rejected": rejected}, indent=2))
    return 1 if rejected else 0


if __name__ == "__main__":
    sys.exit(main())
