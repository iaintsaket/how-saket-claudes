# Skill standard

Every skill in this repo follows the open **[Agent Skills specification](https://agentskills.io/specification)**, the format Anthropic published and that Claude Code, Codex and other agent harnesses read. On top of the spec, these house rules keep quality consistent. `tools/validate_skills.py` checks everything marked **[checked]**.

## 1. Layout

```
skills/<skill-name>/
├── SKILL.md          # required: frontmatter + instructions
├── scripts/          # optional: executable code the agent runs
├── references/       # optional: docs the agent reads on demand
└── assets/           # optional: templates, data, static files
```

- One skill per folder. The folder name equals `name` **[checked]**.
- No README or LICENSE inside a skill folder. `SKILL.md` is the documentation, and the repo LICENSE covers every skill.
- File references in `SKILL.md` are relative to the skill root and **one level deep**: `references/x.md`, not a chain of files pointing to more files. Every referenced file exists **[checked]**.

## 2. Frontmatter

```yaml
---
name: kebab-case-name            # required: ≤64 chars, a-z 0-9 and single hyphens [checked]
description: >-                  # required: ≤1024 chars [checked]
  Does X for Y. Use when the user says "...", "...", or asks about Z.
  Not for W.
license: MIT                     # required in this repo [checked]
compatibility: Needs ...         # only if it needs tools, network or a specific harness (≤500 chars) [checked]
metadata:
  author: iaintsaket             # required in this repo [checked]
  version: "1.0.0"               # required, semver; bump on every change [checked]
---
```

**The description is the trigger.** At startup, only `name` and `description` are loaded for every skill. Write it in the third person, say *what it does* and *when to use it*, and list the actual phrases users type. Add a "Not for…" clause when a neighbouring skill could be confused with it.

## 3. Body

Keep `SKILL.md` **under 500 lines [checked]**, roughly 5k tokens. Move catalogues, long templates and edge-case detail into `references/` and say *when* to read each file.

Recommended skeleton. Use the sections that apply, in this order:

1. `# Title` and one short paragraph: the job and the quality bar.
2. **Inputs / invocation**: how to read `$ARGUMENTS` or the request, what to default, and when (rarely) to ask.
3. **Workflow**: numbered phases or steps, each with a goal and the concrete commands.
4. **Output**: exact format, where files are saved, and what the chat reply contains.
5. **Rules / gotchas**: non-negotiables and known failure modes.
6. **Files**: one line per `references/`, `scripts/` or `assets/` file and when to use it.

## 4. Writing rules

- **Imperative and concise.** Assume a capable agent. Explain *why* only where it changes behaviour, and don't teach what the model already knows.
- **One term per concept** throughout a skill.
- **No stale facts.** Avoid hardcoded years and versions. Say "current year" or "as of <date>, verify with search".
- **Portable tool names.** Don't hardcode one harness's private tool IDs. Write "a structured question tool such as AskUserQuestion, if available" and give a fallback.
- **Deterministic work goes in scripts.** Validation, link checks and calculations are scripts with clear errors and non-zero exit codes, not prose instructions.
- **Never fabricate.** Any skill that researches must say how claims and links are verified.

## 5. Safety and privacy [checked]

- No secrets, tokens, API keys or private URLs. User-specific config lives *outside* the repo (for example `~/.claude/<skill>-config.json`) and is documented in `references/`.
- No absolute personal paths (`/Users/<name>`, `/home/<name>`). Use `~` or an env var such as `BUG_BOUNTY_HOME`.
- Security skills state their scope (authorized targets, local clones) in both the description and the rules.

## 6. Change process

1. Edit the skill and bump `metadata.version`: patch for wording, minor for new behaviour, major for a changed interface.
2. Run `python3 tools/validate_skills.py` until it passes. CI runs the same check on every push.
3. Try the skill once on a real prompt before merging.

Start a new skill from `templates/SKILL.template.md`.
