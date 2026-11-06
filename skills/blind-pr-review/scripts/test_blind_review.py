"""Tests for the blind-pr-review scripts. Run: python3 test_blind_review.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import loop_state  # noqa: E402
import prepare_review  # noqa: E402
import run_review  # noqa: E402

HIGH = {"severity": "High", "file": "a.py", "class": "path-traversal"}
LOW = {"severity": "Low", "file": "b.py", "class": "weak-header"}


def fresh() -> dict:
    return {"rounds": [], "disputes": []}


class Loop(unittest.TestCase):
    def test_two_clean_rounds_on_one_head_pass(self):
        s = fresh()
        self.assertEqual(loop_state.record(s, "h1", [])["decision"], "REVIEW")
        self.assertEqual(loop_state.record(s, "h1", [])["decision"], "PASS")

    def test_a_new_head_restarts_the_clean_count(self):
        s = fresh()
        loop_state.record(s, "h1", [])
        self.assertEqual(loop_state.record(s, "h2", [])["decision"], "REVIEW")
        self.assertEqual(loop_state.record(s, "h2", [])["decision"], "PASS")

    def test_a_blocking_finding_needs_a_fix(self):
        self.assertEqual(loop_state.record(fresh(), "h1", [HIGH])["decision"], "FIX")

    def test_a_finding_between_clean_rounds_resets_the_count(self):
        s = fresh()
        loop_state.record(s, "h1", [])
        loop_state.record(s, "h1", [HIGH])
        self.assertEqual(loop_state.record(s, "h1", [])["decision"], "REVIEW")

    def test_low_findings_do_not_block_but_are_kept_for_the_human(self):
        s = fresh()
        loop_state.record(s, "h1", [LOW])
        out = loop_state.record(s, "h1", [])
        self.assertEqual(out["decision"], "PASS")
        self.assertEqual(out["low"], [LOW])

    def test_the_round_cap_escalates(self):
        s = fresh()
        for n in range(4):
            self.assertEqual(loop_state.record(s, f"h{n}", [dict(HIGH, file=f"{n}.py")])["decision"], "FIX")
        self.assertEqual(loop_state.record(s, "h4", [dict(HIGH, file="4.py")])["decision"], "ESCALATE")

    def test_passing_on_the_last_round_still_passes(self):
        s = fresh()
        for n in range(3):
            loop_state.record(s, f"h{n}", [dict(HIGH, file=f"{n}.py")])
        loop_state.record(s, "h9", [])
        self.assertEqual(loop_state.record(s, "h9", [])["decision"], "PASS")

    def test_a_finding_back_after_a_fix_escalates(self):
        s = fresh()
        loop_state.record(s, "h1", [HIGH])
        self.assertEqual(loop_state.record(s, "h2", [HIGH])["decision"], "ESCALATE")

    def test_two_reviewers_agreeing_on_one_head_is_not_a_failed_fix(self):
        s = fresh()
        loop_state.record(s, "h1", [HIGH])
        self.assertEqual(loop_state.record(s, "h1", [HIGH])["decision"], "FIX")

    def test_a_dispute_always_escalates_even_after_clean_rounds(self):
        s = fresh()
        loop_state.record(s, "h1", [HIGH])
        loop_state.dispute(s, loop_state.fingerprint(HIGH), "no failing test possible")
        loop_state.record(s, "h2", [])
        self.assertEqual(loop_state.record(s, "h2", [])["decision"], "ESCALATE")

    def test_the_author_cannot_write_pass_into_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = Path(tmp) / "f.json"
            findings.write_text(json.dumps({"findings": [HIGH]}))
            state = Path(tmp) / "s.json"
            cmd = [sys.executable, str(Path(loop_state.__file__)), "--state", str(state)]
            done = subprocess.run(
                cmd + ["record", "--head", "h1", "--findings", str(findings)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(done.returncode, loop_state.EXIT["FIX"], done.stderr)
            self.assertEqual(json.loads(done.stdout)["decision"], "FIX")
            self.assertEqual(len(json.loads(state.read_text())["rounds"]), 1)


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return done.stdout.strip()


class Prepare(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name) / "repo"
        self.repo.mkdir()
        self.out = Path(tmp.name) / "out"
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "base.py").write_text("base = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "checkout", "-q", "-b", "pr")
        (self.repo / ".gitattributes").write_text("hidden.py export-ignore\nmasked.py -diff\n")
        (self.repo / "hidden.py").write_text("HIDDEN_FILE_BODY = 1\n")
        (self.repo / "masked.py").write_text("MASKED_CHANGE = 1\n")
        (self.repo / "link.py").symlink_to("/etc/hosts")
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "x.py").write_text("x = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "AUTHOR_EXPLANATION_MARKER")
        self.head = git(self.repo, "rev-parse", "HEAD")
        git(self.repo, "checkout", "-q", "main")
        (self.repo / "later.py").write_text("LATER_ON_BASE = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "later")
        self.manifest = prepare_review.prepare(self.repo, "main", self.head, self.out)

    def test_files_a_pr_hides_with_export_ignore_are_still_reviewed(self):
        self.assertIn("HIDDEN_FILE_BODY", (self.out / "code" / "hidden.py").read_text())

    def test_changes_a_pr_marks_as_binary_still_show_in_the_diff(self):
        self.assertIn("MASKED_CHANGE", (self.out / "change.diff").read_text())

    def test_symlinks_are_not_followed_out_of_the_review_folder(self):
        self.assertFalse((self.out / "code" / "link.py").is_symlink())
        self.assertFalse((self.out / "code" / "link.py").exists())
        self.assertIn("link.py", self.manifest["skipped"])

    def test_nothing_from_the_author_reaches_the_reviewer(self):
        self.assertFalse((self.out / "code" / ".git").exists())
        for path in self.out.rglob("*"):
            if path.is_file():
                self.assertNotIn("AUTHOR_EXPLANATION_MARKER", path.read_text())

    def test_the_diff_covers_only_the_pr_not_later_base_commits(self):
        self.assertNotIn("LATER_ON_BASE", (self.out / "change.diff").read_text())

    def test_nested_files_keep_their_paths(self):
        self.assertTrue((self.out / "code" / "sub" / "x.py").is_file())

    def test_a_file_path_cannot_escape_the_folder(self):
        with self.assertRaises(ValueError):
            prepare_review.safe_target(self.out / "code", "../outside.py")


GOOD = {
    "severity": "High",
    "class": "path-traversal",
    "title": "Spec path reads any file",
    "file": "a.py",
    "line": 2,
    "input": "symbol from the request",
    "boundary": "request to filesystem",
    "path": "handler to open()",
    "gain": "read any file",
    "loss": "tokens exposed",
}


class Run(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.code = Path(tmp.name)
        (self.code / "a.py").write_text("one\ntwo\n")

    def test_the_reviewer_can_only_read(self):
        cmd = run_review.build_cmd("prompt")
        tools = cmd[cmd.index("--tools") + 1 :]
        self.assertEqual(sorted(tools), ["Glob", "Grep", "Read"])
        self.assertNotIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--setting-sources") + 1], "")
        self.assertEqual(cmd[cmd.index("--permission-mode") + 1], "dontAsk")
        self.assertIn("--strict-mcp-config", cmd)
        self.assertIn("--no-session-persistence", cmd)

    def test_no_blanket_allow_rule_opens_the_whole_disk(self):
        # A live probe read a marker in the home folder while Read was on --allowedTools.
        # dontAsk with no allow rules keeps tools inside the working folder.
        self.assertNotIn("--allowedTools", run_review.build_cmd("prompt"))

    def test_the_reviewer_inherits_no_secrets_from_the_environment(self):
        env = run_review.review_env({"HOME": "/h", "PATH": "/p", "GH_TOKEN": "x", "AWS_KEY": "y"})
        self.assertEqual(env["HOME"], "/h")
        self.assertNotIn("GH_TOKEN", env)
        self.assertNotIn("AWS_KEY", env)

    def test_a_finding_meeting_the_contract_is_kept(self):
        kept, dropped = run_review.filter_findings([GOOD], self.code)
        self.assertEqual((kept, dropped), ([GOOD], []))

    def test_a_finding_missing_part_of_the_contract_is_dropped(self):
        for field in ("input", "boundary", "path", "gain", "loss", "class"):
            bad = {k: v for k, v in GOOD.items() if k != field}
            kept, dropped = run_review.filter_findings([bad], self.code)
            self.assertEqual(kept, [], field)
            self.assertEqual(len(dropped), 1)

    def test_a_finding_citing_code_that_does_not_exist_is_dropped(self):
        for change in ({"file": "nope.py"}, {"line": 99}, {"line": 0}, {"file": "../a.py"}):
            kept, _ = run_review.filter_findings([dict(GOOD, **change)], self.code)
            self.assertEqual(kept, [], change)

    def test_an_unknown_severity_is_dropped(self):
        kept, _ = run_review.filter_findings([dict(GOOD, severity="Urgent")], self.code)
        self.assertEqual(kept, [])

    def test_a_reply_that_cannot_be_parsed_is_an_error_not_a_clean_review(self):
        with self.assertRaises(ValueError):
            run_review.parse_reply("Looks good to me!")
        with self.assertRaises(ValueError):
            run_review.parse_reply('{"verdict": "fine"}')

    def test_a_reply_wrapped_in_prose_still_parses(self):
        self.assertEqual(run_review.parse_reply('Here:\n{"findings": []}\nDone.'), [])


if __name__ == "__main__":
    unittest.main()
