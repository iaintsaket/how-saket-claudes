# Hooks setup

Add these to `hooks` in `~/.claude/settings.json`, merging with any existing hooks:

```json
{
  "UserPromptSubmit": [{ "hooks": [{ "type": "command", "command": "python3 -I ~/.claude/skills/progress-log/scripts/compact_guard.py remind" }] }],
  "PreCompact": [{ "hooks": [{ "type": "command", "command": "python3 -I ~/.claude/skills/progress-log/scripts/compact_guard.py rules" }] }],
  "SessionStart": [
    { "hooks": [{ "type": "command", "command": "python3 -I ~/.claude/skills/progress-log/scripts/compact_guard.py locate" }] },
    { "matcher": "compact", "hooks": [{ "type": "command", "command": "python3 -I ~/.claude/skills/progress-log/scripts/compact_guard.py restore" }] }
  ]
}
```

- `remind` reads the context size from the transcript. The first reminder comes at 150,000 tokens, then one more every 100,000. To change this, set `CONTEXT_REMIND_TOKENS` and `CONTEXT_REMIND_STEP` under `env` in settings.
- `rules` prints `assets/compact-rules.md`. Plain output from a PreCompact hook becomes the compaction instructions, capped at 10,000 characters.
- `locate` runs when a chat starts, resumes or clears. It tells the model that chat's log path, `~/.claude/progress/<session id>.md`, so two chats never share a log.
- `restore` prints the last 8,000 characters of that chat's log after a compaction.
