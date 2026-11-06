#!/usr/bin/env python3
"""Flag vague or unnecessary content in skill Markdown, on exact lines.

    lint_skill.py [--base REF] [--all] [--json]

--base checks only the lines added since REF, which is what a PR comments on.
--all checks every line of every skill. Exit 0 is clean, 1 means findings.
To keep a line on purpose, end it with <!-- skill-lint: allow RULE -->.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

VAGUE = re.compile(
    r"\b(etc\.?|and so on|and more|as needed|as appropriate|if appropriate|when appropriate"
    r"|if necessary|when necessary|where possible|if possible|appropriately|properly"
    r"|best practices?|high[- ]quality|good quality|robust|comprehensive|thoroughly"
    r"|try to|should probably|might want to|various)\b",
    re.I,
)
FILLER = re.compile(
    r"\b(please|note that|it is important to|it's important to|in order to|simply|basically"
    r"|obviously|feel free|make sure to|be sure to|remember to)\b",
    re.I,
)
PERSONA = re.compile(r"\byou are (an? )?(expert|world-class|helpful|seasoned)\b", re.I)
PLACEHOLDER = re.compile(r"(?<![-\w])(TODO|TBD|FIXME|XXX)\b|lorem ipsum")
WHEN = re.compile(r"\buse (when|before|after|for)\b", re.I)
HEADING = re.compile(r"^(#{1,6})\s")
ALLOW = re.compile(r"<!--\s*skill-lint:\s*allow\s+([\w-]+)\s*-->")
NOISE = re.compile(r"`[^`]*`|\"[^\"]*\"|“[^”]*”|<!--.*?-->")
SKIP_FILES = re.compile(r"(^|/)(test_[^/]*|__pycache__(/.*)?|[^/]*\.pyc|\.DS_Store)$")
MIN_DUPLICATE = 40

MESSAGES = {
    "vague-phrase": "Vague: `{}` can't be acted on or checked. State the exact condition, step or list.",
    "filler": "Unnecessary: `{}` adds nothing. Cut it and keep the instruction.",
    "persona": "Unnecessary: a persona doesn't change behaviour. State the job instead.",
    "placeholder": "Unfinished: `{}` is a placeholder. Finish this or remove it.",
    "empty-section": "Unnecessary: this section is empty. Add its content or remove it.",
    "duplicate-line": "Unnecessary: this repeats an earlier line. Keep one.",
    "description-trigger": "Vague: the description must say when to use the skill, with `Use when`.",
    "unreferenced-file": "Unnecessary: SKILL.md never mentions this file. Reference it or delete it.",
}


def finding(path, line, rule, text, detail=""):
    return {"file": path, "line": line, "rule": rule, "text": text.strip(),
            "message": MESSAGES[rule].format(detail)}


def body_lines(text):
    """Yield (line number, line) outside code fences, plus each fence line."""
    fenced = False
    for number, line in enumerate(text.split("\n"), 1):
        is_fence = line.lstrip().startswith("```")
        if is_fence:
            fenced = not fenced
        if is_fence or not fenced:
            yield number, line


def frontmatter(text):
    """Return ({key: value}, {key: line}) for the top-level keys."""
    lines = text.split("\n")
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        return {}, {}
    values, numbers, key = {}, {}, None
    for number, line in enumerate(lines[1:lines.index("---", 1)], 2):
        top = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if top:
            key = top.group(1)
            values[key], numbers[key] = top.group(2), number
        elif key:
            values[key] += " " + line.strip()
    return values, numbers


def word_rules(path, number, line, allowed):
    if line.lstrip().startswith("|"):
        return  # Table rows are data.
    clean = NOISE.sub("", line)
    for rule, pattern in (("vague-phrase", VAGUE), ("filler", FILLER),
                          ("persona", PERSONA), ("placeholder", PLACEHOLDER)):
        match = pattern.search(clean)
        if match and rule not in allowed:
            yield finding(path, number, rule, line, match.group(0))


def structure_rules(path, rows):
    seen = set()
    for index, (number, line) in enumerate(rows):
        allowed = ALLOW.findall(line)
        stripped = line.strip()
        heading = HEADING.match(line)
        if heading and "empty-section" not in allowed:
            following = next((r[1] for r in rows[index + 1:] if r[1].strip()), None)
            child = HEADING.match(following) if following else None
            if following is None or (child and len(child.group(1)) <= len(heading.group(1))):
                yield finding(path, number, "empty-section", line)
        if len(stripped) >= MIN_DUPLICATE and not heading and not stripped.startswith("|"):
            if stripped in seen and "duplicate-line" not in allowed:
                yield finding(path, number, "duplicate-line", line)
            seen.add(stripped)


def skill_rules(path, text, files):
    values, numbers = frontmatter(text)
    if "description" in values and not WHEN.search(values["description"]):
        yield finding(path, numbers["description"], "description-trigger", values["description"][:80])
    root = str(Path(path).parent)
    for relative in files:
        folders = [str(p) + "/" for p in Path(relative).parents if str(p) != "."]
        mentions = [relative, Path(relative).name] + folders
        if SKIP_FILES.search(relative) or any(m in text for m in mentions):
            continue
        yield finding("{}/{}".format(root, relative), 1, "unreferenced-file", relative)


def lint_text(path, text, files):
    rows = list(body_lines(text))
    found = []
    for number, line in rows:
        found.extend(word_rules(path, number, line, ALLOW.findall(line)))
    found.extend(structure_rules(path, rows))
    if Path(path).name == "SKILL.md":
        found.extend(skill_rules(path, text, files))
    return found


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


def in_diff(findings, added):
    return [f for f in findings if f["line"] in added.get(f["file"], set())]


def skill_files(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and p.name != "SKILL.md")


def lint_repo(skills):
    found = []
    for skill in sorted(p for p in skills.iterdir() if (p / "SKILL.md").is_file()):
        references = sorted((skill / "references").glob("*.md"))
        texts = "\n".join(extra.read_text() for extra in references)
        files = [f for f in skill_files(skill) if Path(f).name not in texts]
        found.extend(lint_text(str(skill / "SKILL.md"), (skill / "SKILL.md").read_text(), files))
        for extra in references:
            found.extend(lint_text(str(extra), extra.read_text(), []))
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--base", help="check only lines added since this git ref")
    parser.add_argument("--all", action="store_true", help="check every line")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if bool(args.base) == args.all:
        parser.error("pass exactly one of --base or --all")

    found = lint_repo(Path("skills"))
    if args.base:
        diff = subprocess.run(["git", "diff", "--no-color", "-U0", args.base + "...HEAD", "--", "skills"],
                              capture_output=True, text=True, check=True).stdout
        found = in_diff(found, added_lines(diff))
    if args.json:
        print(json.dumps(found, indent=2))
    else:
        for item in found:
            print("{file}:{line}: [{rule}] {message}".format(**item))
        print("{} finding(s)".format(len(found)))
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
