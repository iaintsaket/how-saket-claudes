---
name: token-audit
description: >-
  Measures where Claude Code tokens go, from the local session transcripts: context per API
  call, the costliest sessions and what they ran, the tools whose results fill the context, and
  files read again and again. Then it names the few changes that would save the most, such as
  batching shell steps into one script ("code mode"). Use when the user says "token audit",
  "where do my tokens go", "why is my usage so high", "reduce token usage", "is code mode worth
  it for me", or "/token-audit". Not for API billing or pricing questions.
license: MIT
compatibility: Needs Python 3.10+ and Claude Code transcripts in ~/.claude/projects.
metadata:
  author: iaintsaket
  version: "0.1.0"
---

# Token Audit

Find out, from real numbers, what uses the user's tokens and what would cut it. Every tool call re-sends the whole conversation, so the count of calls in long sessions usually costs more than any one large result. Good output names the two or three biggest causes with numbers, and a fix for each.

## Inputs

`$ARGUMENTS` / the request:
- Empty → audit every transcript.
- A date (`since 2026-11-01`) → pass `--since YYYY-MM-DD`. To judge a change, run once with `--since <date of change>` and once without, and compare context per call and calls per session.

## Workflow

1. **Measure.** Run `python3 scripts/token_audit.py --top 10` (add `--since`). It reads `~/.claude/projects/*/*.jsonl`, counts each API response once and prints a short report. Use `--format json` when you need exact fields. Do not read the transcripts yourself: they are large, and the script exists so their contents stay out of the context.
2. **Diagnose.** Read the report in this order:
   - **Context per call.** Over about 100k means long sessions; every call re-reads that much.
   - **Costliest sessions.** Many `Bash` calls in one session means shell steps were run one at a time.
   - **Tool results.** A script or MCP server near the top returns more than the model needs.
   - **Files read 3+ times.** Large files re-read in full.
3. **Recommend.** Give at most four fixes, biggest saving first, each tied to a number in the report:
   - Many small shell calls → batch them into one script that prints only a summary (code mode with the harness's own tools), and say so in the user's CLAUDE.md.
   - High context per call → `/clear` or `/compact` between unrelated tasks.
   - A chatty script or MCP tool → make it filter and print a summary; for an MCP server with many tools, keep its tools deferred or wrap it in a script.
   - Repeated reads → search first and read line ranges; split a file that is read often.
   - Searches across many files → a read-only subagent, so only its conclusion enters the context.
4. **Apply on request.** Change config, CLAUDE.md or scripts only when the user asks.

## Output

A reply of under 250 words: the totals line, a table of the top causes (cause, number, fix), and one line on what to re-run later (`--since <today>`) to see whether the fixes worked.

## Rules

- Report estimates as estimates. Tool-result tokens are characters / 4, and an image is counted apart because its base64 size is not what it costs.
- Cache reads are billed at a fraction of normal input, so say how heavily cached the usage is before calling a number expensive.
- The report holds the user's prompts and file paths. Keep it local; never paste it into a public issue, PR or post.
- Never claim a saving you did not measure. After a change, re-run with `--since` and report the before and after numbers.

## Files

- `scripts/token_audit.py`: run at step 1. `--projects DIR`, `--since YYYY-MM-DD`, `--top N`, `--format text|json`. Reads only; writes nothing.
- `scripts/test_token_audit.py`: run after changing the script.
