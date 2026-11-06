Write the shortest summary that lets work continue without re-asking the user. Assume progress.md and the repository are still available.

KEEP:
- The user's current goal and what they asked for, in their own words where it matters.
- The user's decisions, corrections and stated preferences.
- Unfinished subtasks and the exact next step.
- Paths of files changed or being worked on, as paths only.
- Unresolved errors, with the exact message.
- Commands that were confirmed to work, such as how to run the tests.
- Failed approaches, in one line each, so they are not tried again.
- Open questions and anything waiting on the user.

REMOVE:
- File contents, code blocks and diffs. They can be read again from disk.
- Tool output, logs, search results and command output.
- Web pages, documentation and schemas already read. Keep the URL and the conclusion.
- Finished subtasks. Their record is in progress.md.
- Debugging steps that led to a fix, except the failed approaches kept above. Keep the root cause if it may recur.
- Text from loaded skills, and instructions that are already in CLAUDE.md.
- Exploration that ended up unused, greetings and progress narration.

Never invent details. If something is uncertain, say so.
