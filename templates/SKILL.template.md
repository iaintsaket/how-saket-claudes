---
name: skill-name
description: >-
  Does <what> for <whom/what input>, producing <output>. Use when the user says
  "<trigger phrase>", "<another phrase>", or asks about <topic>. Not for <neighbouring task>.
license: MIT
metadata:
  author: iaintsaket
  version: "0.1.0"
---

# Skill Title

<One short paragraph: the job, who it's for, and what "good" looks like.>

## Inputs

`$ARGUMENTS` / the request:
- Empty → <default behaviour, or the one question to ask>.
- <pattern> → <behaviour>.

## Workflow

1. **<Phase name>.** <Goal.> <Concrete commands or actions.>
2. **<Phase name>.** …

## Output

- <Exact format / file path / what the chat reply contains.>

## Rules

- <Non-negotiable.>
- <Known failure mode and how to avoid it.>

## Files

- `references/<file>.md`: read when <condition>.
- `scripts/<file>.py`: run to <purpose>.
