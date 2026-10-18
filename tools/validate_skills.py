#!/usr/bin/env python3
"""Validate every skill against STANDARD.md (Agent Skills spec + house rules).

Usage: python3 tools/validate_skills.py [skills_dir]   (default: ./skills)
Exits non-zero if any skill has an error. Warnings don't fail the run.
Standard library only; the frontmatter parser handles the subset of YAML we use.
"""
import re, sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SECRET_RES = [
    re.compile(p) for p in (
        r"sk-[A-Za-z0-9_-]{20,}", r"gh[pousr]_[A-Za-z0-9]{20,}", r"AKIA[0-9A-Z]{16}",
        r"xox[baprs]-[A-Za-z0-9-]{10,}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"script\.google\.com/macros/s/[A-Za-z0-9_-]{20,}",
    )
]
PERSONAL_PATH_RE = re.compile(r"/(Users|home)/[A-Za-z0-9._-]+/")
REF_RE = re.compile(r"`((?:references|scripts|assets)/[^`\s*<>]+)`")
TEXT_EXT = {".md", ".py", ".sh", ".js", ".ts", ".json", ".html", ".txt", ".yaml", ".yml", ".toml"}


def parse_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return None, text
    data, key, block = {}, None, None
    lines = m.group(1).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        top = re.match(r"^([A-Za-z][\w-]*):\s*(.*)$", line)
        if top:
            key, val = top.group(1), top.group(2).strip()
            if val in (">", ">-", "|", "|-", ""):
                # folded/literal scalar or a nested map
                body = []
                i += 1
                while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                    body.append(lines[i])
                    i += 1
                nested = [re.match(r"^\s+([\w-]+):\s*(.*)$", b) for b in body if b.strip()]
                if val == "" and nested and all(nested):
                    data[key] = {n.group(1): n.group(2).strip().strip('"\'') for n in nested}
                else:
                    joiner = "\n" if val.startswith("|") else " "
                    data[key] = joiner.join(b.strip() for b in body).strip()
                continue
            data[key] = val.strip('"\'')
        i += 1
    return data, text[m.end():]


def check_skill(d: Path):
    errors, warns = [], []
    f = d / "SKILL.md"
    if not f.exists():
        return [f"missing SKILL.md"], warns
    text = f.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    if fm is None:
        return ["SKILL.md has no YAML frontmatter"], warns

    name = fm.get("name", "")
    if not name:
        errors.append("frontmatter: `name` is required")
    elif not NAME_RE.match(name) or len(name) > 64:
        errors.append(f"frontmatter: invalid name {name!r} (≤64, a-z0-9, single hyphens)")
    elif name != d.name:
        errors.append(f"frontmatter: name {name!r} must equal folder name {d.name!r}")

    desc = fm.get("description", "")
    if not desc:
        errors.append("frontmatter: `description` is required")
    elif len(desc) > 1024:
        errors.append(f"frontmatter: description is {len(desc)} chars (max 1024)")
    elif not re.search(r"\bUse (when|for)\b", desc):
        warns.append("description should say when to use the skill ('Use when …')")

    if fm.get("license") != "MIT":
        errors.append("frontmatter: `license: MIT` is required in this repo")
    comp = fm.get("compatibility")
    if comp is not None and not (1 <= len(comp) <= 500):
        errors.append("frontmatter: compatibility must be 1–500 chars")
    meta = fm.get("metadata")
    if not isinstance(meta, dict):
        errors.append("frontmatter: `metadata` map with author and version is required")
    else:
        if not meta.get("author"):
            errors.append("metadata.author is required")
        if not re.match(r"^\d+\.\d+\.\d+$", meta.get("version", "")):
            errors.append("metadata.version must be semver, e.g. \"1.0.0\"")
    unknown = set(fm) - {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    if unknown:
        errors.append(f"frontmatter: unknown fields {sorted(unknown)}")

    n_lines = text.count("\n") + 1
    if n_lines > 500:
        errors.append(f"SKILL.md is {n_lines} lines (max 500); move detail into references/")

    for ref in sorted(set(REF_RE.findall(body))):
        if not (d / ref).exists():
            errors.append(f"referenced file not found: {ref}")

    for extra in ("README.md", "LICENSE", "LICENSE.txt"):
        if (d / extra).exists():
            warns.append(f"{extra} inside a skill folder; the repo-level one covers it")

    for p in d.rglob("*"):
        if not p.is_file() or p.suffix not in TEXT_EXT:
            continue
        rel = p.relative_to(d)
        content = p.read_text(encoding="utf-8", errors="ignore")
        for rx in SECRET_RES:
            if rx.search(content):
                errors.append(f"possible secret in {rel} ({rx.pattern[:24]}…)")
        if PERSONAL_PATH_RE.search(content):
            errors.append(f"absolute personal path in {rel}; use ~ or an env var")
    return errors, warns


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "skills")
    dirs = sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith("."))
    if not dirs:
        sys.exit(f"no skills found in {root}")
    failed = 0
    for d in dirs:
        errors, warns = check_skill(d)
        status = "FAIL" if errors else "ok  "
        print(f"{status} {d.name}")
        for e in errors:
            print(f"     error: {e}")
        for w in warns:
            print(f"     warn:  {w}")
        failed += bool(errors)
    print(f"\n{len(dirs)} skills, {failed} failing")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
