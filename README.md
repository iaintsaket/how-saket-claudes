# how-saket-claudes

Agent skills I use with [Claude Code](https://claude.com/claude-code). Every skill follows the open [Agent Skills specification](https://agentskills.io/specification) plus the house rules in [STANDARD.md](STANDARD.md), so other harnesses that read `SKILL.md` folders (such as Codex) can load them too.

| Skill | What it does | Try |
|---|---|---|
| [course-builder](skills/course-builder) | Researches a tech topic and publishes a compact interactive course: modules, verified docs, blogs and YouTube videos, a hands-on task and a quiz per module | `create a course on Apache Pulsar` |
| [bug-hunt](skills/bug-hunt) | Bug-bounty-grade source audit of a local clone: architecture first, source→sink taint tracing, validation, differential PoCs, report saved to disk | `/bug-hunt https://github.com/org/repo` |
| [bug-review](skills/bug-review) | Adversarial triage of a finding before submission. Returns NOT_A_BUG, NEEDS_REVISION or VALID, and loops with bug-hunt up to 3 times | `/bug-review ~/bug_bounty/findings/<repo>/<finding>` |
| [mock-interview](skills/mock-interview) | Timed, brutally honest DSA or LLD mock interview with a Hire/No Hire verdict and an optional Google Sheets progress log | `/mock-interview LLD` |
| [trip-itinerary](skills/trip-itinerary) | Hour-by-hour trip plans with live place research, hotel tiers, transport comparisons and budgets, with extra depth for India | `plan a 5-day trip to Rajasthan` |

## Install

```bash
git clone git@github.com:iaintsaket/how-saket-claudes.git ~/my_codes/how-saket-claudes
mkdir -p ~/.claude/skills
for s in ~/my_codes/how-saket-claudes/skills/*/; do ln -sfn "$s" ~/.claude/skills/$(basename "$s"); done
```

The symlinks keep the repo as the single source of truth, so `git pull` updates every skill. For other harnesses, link into `~/.agents/skills/` instead.

## Add or change a skill

1. Copy [templates/SKILL.template.md](templates/SKILL.template.md) to `skills/<name>/SKILL.md`, or edit an existing skill and bump `metadata.version`.
2. Run `python3 tools/validate_skills.py`. It checks the spec plus the house rules: line budget, referenced files exist, and no secrets or personal paths. CI also runs the official `skills-ref` validator.

## Credits

`course-builder` borrows ideas from [zarazhangrui/codebase-to-course](https://github.com/zarazhangrui/codebase-to-course) (application-style quizzes, writing modules one at a time), [jacquardlabs/study-skills](https://github.com/jacquardlabs/study-skills) (dependency-ordered concepts, never inventing citations) and [derwells/skills](https://github.com/derwells/skills) (lessons framed around a question).

## License

MIT
