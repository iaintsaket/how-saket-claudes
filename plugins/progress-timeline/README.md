# progress-timeline

A Claude Code mod that shows the chat's progress log as a timeline in a pane beside the chat. It opens by itself when a plan is ready.

```
                       2026-11-06
                            │
╭─────────────────────────╮ │
│ Skill verifier        › │─◉  In progress
│ 2026-11-06 · 2/4        │ │
╰─────────────────────────╯ │
                            │
                         Planned
                            │
                            │ ╭─────────────────────────╮
                   Planned  ○─│ Next tasks, in order… › │
                            │ │ No date · 0/5           │
                            │ ╰─────────────────────────╯
```

## Install

From a shell:

```bash
claude plugin install progress-timeline --marketplace iaintsaket/how-saket-claudes
```

Or at the prompt of a terminal session:

```
/plugin install progress-timeline --marketplace iaintsaket/how-saket-claudes
```

Accept the marketplace, and keep the user scope so the mod runs in every new session.

## When the pane opens

- A new `## ` section appears in the chat's log. It checks the file every 2 seconds.
- A chat is resumed and its log already has sections.
- You approve a plan in plan mode.

Run `/progress-timeline` to open it at any other time. If you close it, it stays closed until the next new plan. Claude Code shows an unrequested pane only in a wide enough terminal: its docs give 144 columns, or 110 in some cases. In a narrower one, run `/progress-timeline`.

## The file it reads

It reads this chat's own log, `~/.claude/progress/<session id>.md`, which the `progress-log` skill writes, so two chats never show each other's progress. It only reads the file, and needs this format:

```markdown
## Task name (2026-11-06)
- [x] A finished step
- [ ] The next step
```

Each `## ` section is a card, and each checkbox is a step inside it. A section without a date goes under a `Planned` badge. The [progress-log](../../skills/progress-log) skill keeps this file up to date, but any tool or person can write it.

## Using the pane

- The pane asks for a sixth of the screen, with a minimum of 24 columns. At that width the cards stack on one side of the line. They alternate from 44 columns up.
- Drag the pane's edge to resize it. Claude Code keeps that width across sessions, and it overrides what the mod asks for. It docks on the right, and Claude Code has no setting to move it.
- Green `●` is done, yellow `◉` is in progress, grey `○` is planned.
- Click `›` to open a card and read its steps in full.
- With the keyboard: `ctrl+x tab` focuses the pane, `Tab` moves to a card's arrow, and `Enter` opens it.

## Develop

```bash
claude plugin test plugins/progress-timeline
claude plugin validate plugins/progress-timeline
claude --plugin-dir plugins/progress-timeline
```

The last command runs a session with your local copy loaded.
