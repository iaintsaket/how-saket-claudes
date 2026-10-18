---
name: repo-bootstrap
description: >-
  Creates or hardens a GitHub repository so it starts safe: public unless the
  user asks for private, a CI workflow that lints, tests and fails under 80%
  line coverage, and a ruleset on the default branch (no direct pushes,
  force-pushes or deletion; merges only through a PR with green CI). Use
  when a new repo is being created or first pushed ("create a repo",
  "make a new GitHub repo", "gh repo create", "init this project and push it",
  "publish this to GitHub"), or when the user says "add branch protection",
  "set up CI and coverage", or "harden this repo". Not for reviewing code or
  fixing a failing test suite.
license: MIT
compatibility: Needs git, python3 and the GitHub CLI (gh) logged in with the repo scope.
metadata:
  author: iaintsaket
  version: "1.0.0"
---

# Repo Bootstrap

Every repo the user creates gets the same baseline, with no reminders needed: **public by default**, **CI on every PR and push**, **a minimum of 80% line coverage enforced in CI**, and **the default branch protected by a ruleset** whose required check is that CI job. Done means `scripts/verify_repo.py` passes against the live repo, not that the files were written.

## Inputs

The request, or `$ARGUMENTS`:
- A repo name, or nothing → use the current directory's name and create the repo under the logged-in account (`gh api user --jq .login`).
- `owner/name` → create under that owner (an org the user belongs to).
- Words like "private", "internal" or "don't make it public" → private. Otherwise it is **public**; never ask about visibility.
- An existing repo ("harden this repo", or the current directory already has a GitHub remote) → skip creation and run phases 2–5 against it.
- Coverage: 80% is the floor. A higher number from the user wins; a lower one only if the user insists, and say so in the reply.

Ask only if the stack can't be detected and the directory is empty. Then ask which language, using a structured question tool such as AskUserQuestion if available, or plain chat otherwise.

## Workflow

1. **Preflight.** Run `gh auth status` and confirm the `repo` scope. Make sure the project is a git repo with a `main` default branch (`git init -b main` if needed). Check `gh repo view <owner/name>` to see whether the repo already exists, so you don't create a duplicate.

2. **Detect the stack and scaffold CI.** Detect the stack from its marker file: `pyproject.toml`/`requirements*.txt` → python; `package.json` → node; `go.mod` → go; `Cargo.toml` → rust; `build.gradle*` → java-gradle; `pom.xml` → java-maven. In a monorepo, add one job per stack.
   - Copy `assets/workflows/<stack>.yml` to `.github/workflows/ci.yml`. Keep the job id and name `ci`, because the ruleset requires a check with exactly that name. If you rename it, pass the new name to `apply_protection.sh`.
   - Add the coverage config the stack needs (the threshold lives in the project, so it holds locally too) from `references/coverage.md`.
   - If the repo has no tests yet, add one small real test of real code, so CI is green at 80% from the first commit. Never lower the threshold or exclude source files to pass the check.
   - Add a `.gitignore` for the stack if it is missing, and make sure coverage output (`coverage.out`, `.coverage`, `coverage/`, `lcov.info`) is ignored.
   - Run the same lint, test and coverage commands locally and fix any failures before pushing.

3. **Create the repo and push.** For a new repo:
   ```bash
   gh repo create <owner/name> --public --source . --remote origin --push   # --private only if asked
   ```
   If the repo already exists, push the CI scaffold to `main` before protecting it. Once the ruleset is on, every change needs a PR. Then wait for the first run: `gh run watch -R <owner/name> $(gh run list -R <owner/name> -b main -L1 --json databaseId --jq '.[0].databaseId') --exit-status`. If it fails, fix the problem and push again. Don't protect a branch whose required check is red.

4. **Protect the default branch.** Run:
   ```bash
   bash scripts/apply_protection.sh <owner/name> ci
   ```
   The script creates or updates the ruleset from `assets/ruleset.json` (idempotent), then turns on delete-branch-on-merge, the "update branch" button, and secret scanning with push protection where the plan allows it. If GitHub refuses rulesets on a private repo (free plan), tell the user and offer two fixes: make the repo public, or upgrade the plan. Don't silently skip protection.

5. **Verify.** Run:
   ```bash
   python3 scripts/verify_repo.py <owner/name> --dir . --min-coverage 80
   ```
   It checks visibility, an active ruleset with all four rules and the `ci` check, a workflow on the default branch, a green latest run, and a coverage threshold of 80 or more in the project. Fix everything it reports and re-run until it exits 0.

## Output

A short chat reply covering:
- The repo URL and its visibility.
- The stack, the CI file path, and where the coverage threshold is set, with the current coverage from the first run.
- The ruleset rules and the required check.
- Anything that couldn't be applied and why (for example, secret scanning on a private free repo), plus the `verify_repo.py` result.

From then on, changes land through a branch and a PR: `git switch -c <branch>`, push, then `gh pr create`.

## Rules

- **Public by default.** Only make a repo private when the user says so. Before creating a public repo, scan what will be pushed for secrets (`.env`, keys, tokens). If you find any, stop and tell the user.
- **Order matters:** push the CI first, wait for green, then protect. A ruleset that requires a check that has never passed blocks every PR.
- The required check name must equal the job `name:` in the workflow (`ci`). A mismatch leaves PRs waiting forever on "Expected — waiting for status".
- Never weaken the gate to get green: no lowering the threshold, no `|| true`, no `continue-on-error`, no blanket coverage excludes. Write tests instead.
- Rulesets need no approving review by default (`required_approving_review_count: 0`), so a solo owner can merge their own green PR. Raise it to 1 when the repo has collaborators.
- Use the current major versions of GitHub Actions and language runtimes. The versions in `assets/` are a starting point, so check them before copying.

## Files

- `assets/workflows/<stack>.yml`: the CI templates (python, node, go, rust, java-gradle, java-maven). Copy one to `.github/workflows/ci.yml`.
- `assets/ruleset.json`: the default-branch ruleset that `apply_protection.sh` applies.
- `references/coverage.md`: read in phase 2 for each stack's coverage config and its gotchas.
- `scripts/apply_protection.sh`: run in phase 4 to apply the ruleset and the repo hardening settings.
- `scripts/verify_repo.py`: run in phase 5. Exits non-zero and lists each gap.
