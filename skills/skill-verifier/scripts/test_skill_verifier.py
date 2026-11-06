#!/usr/bin/env python3
"""Tests for lint_skill.py and pr_review.py. Run: python3 test_skill_verifier.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import lint_skill as lint
import pr_review as pr

HEAD = "---\nname: demo\ndescription: >-\n  Does X. Use when the user says \"x\".\nlicense: MIT\n---\n\n"


def rules(text, path="skills/demo/SKILL.md", files=None):
    return [f["rule"] for f in lint.lint_text(path, text, files or [])]


class VagueAndFiller(unittest.TestCase):
    def test_flags_vague_phrase_with_exact_line(self):
        found = lint.lint_text("skills/demo/SKILL.md", HEAD + "# T\n\nFix errors as needed.\n", [])
        self.assertEqual([(f["rule"], f["line"]) for f in found], [("vague-phrase", 10)])

    def test_flags_filler(self):
        self.assertIn("filler", rules(HEAD + "# T\n\nIn order to run, read the file.\n"))

    def test_flags_expert_persona(self):
        self.assertIn("persona", rules(HEAD + "# T\n\nYou are an expert engineer.\n"))

    def test_ignores_code_fences(self):
        self.assertEqual(rules(HEAD + "# T\n\n```bash\n# as needed\n```\n"), [])

    def test_ignores_inline_code_and_quotes(self):
        self.assertEqual(rules(HEAD + "# T\n\nThe word `etc` and \"as needed\" are fine.\n"), [])

    def test_allow_comment_silences_one_rule_on_that_line(self):
        text = HEAD + "# T\n\nFix as needed. <!-- skill-lint: allow vague-phrase -->\n"
        self.assertEqual(rules(text), [])

    def test_allow_comment_does_not_silence_other_rules(self):
        text = HEAD + "# T\n\nIn order to fix. <!-- skill-lint: allow vague-phrase -->\n"
        self.assertEqual(rules(text), ["filler"])


class Structure(unittest.TestCase):
    def test_flags_placeholder(self):
        self.assertIn("placeholder", rules(HEAD + "# T\n\nTODO write this.\n"))

    def test_flags_empty_section(self):
        self.assertIn("empty-section", rules(HEAD + "# T\n\n## Rules\n\n## Files\n\nText.\n"))

    def test_heading_with_child_heading_is_not_empty(self):
        self.assertEqual(rules(HEAD + "# T\n\n## A\n\n### B\n\nText.\n"), [])

    def test_flags_duplicate_line_on_second_use(self):
        line = "Read the whole diff before writing any finding at all."
        found = lint.lint_text("skills/demo/SKILL.md", HEAD + "# T\n\n" + line + "\n\n" + line + "\n", [])
        self.assertEqual([(f["rule"], f["line"]) for f in found], [("duplicate-line", 12)])

    def test_description_must_say_when(self):
        text = "---\nname: demo\ndescription: Does X.\nlicense: MIT\n---\n\n# T\n\nBody.\n"
        found = lint.lint_text("skills/demo/SKILL.md", text, [])
        self.assertEqual([(f["rule"], f["line"]) for f in found], [("description-trigger", 3)])

    def test_flags_file_skill_md_never_mentions(self):
        found = lint.lint_text("skills/demo/SKILL.md", HEAD + "# T\n\nBody.\n", ["references/unused.md"])
        self.assertEqual([(f["rule"], f["file"], f["line"]) for f in found],
                         [("unreferenced-file", "skills/demo/references/unused.md", 1)])

    def test_mentioned_and_test_files_are_fine(self):
        text = HEAD + "# T\n\nRead `references/used.md`.\n"
        self.assertEqual(rules(text, files=["references/used.md", "scripts/test_x.py"]), [])

    def test_only_skill_md_gets_description_and_file_rules(self):
        self.assertEqual(rules("# Brief\n\nBody.\n", path="skills/demo/references/a.md"), [])


class Calibration(unittest.TestCase):
    """False positives found by running the linter on the repo's real skills."""

    def test_section_holding_only_a_code_block_is_not_empty(self):
        self.assertEqual(rules(HEAD + "# T\n\n## A\n\n```\ncode\n```\n\n## B\n\nText.\n"), [])

    def test_table_rows_are_data(self):
        row = "| Area | Budget | Mid-range | Premium | Luxury Resort | Various |"
        self.assertEqual(rules(HEAD + "# T\n\n" + row + "\n\n" + row + "\n"), [])

    def test_hyphenated_identifier_is_not_a_placeholder(self):
        self.assertEqual(rules(HEAD + "# T\n\nReport the CWE-XXX id.\n"), [])

    def test_use_for_counts_as_a_trigger(self):
        text = "---\nname: d\ndescription: Does X. Use for an audit.\nlicense: MIT\n---\n\n# T\n\nBody.\n"
        self.assertEqual(rules(text), [])

    def test_mentioning_a_folder_covers_its_files(self):
        text = HEAD + "# T\n\nCopy from `assets/workflows/`.\n"
        self.assertEqual(rules(text, files=["assets/workflows/go.yml"]), [])


class DiffScope(unittest.TestCase):
    DIFF = "\n".join([
        "diff --git a/skills/demo/SKILL.md b/skills/demo/SKILL.md",
        "--- a/skills/demo/SKILL.md",
        "+++ b/skills/demo/SKILL.md",
        "@@ -3,0 +4,2 @@ context",
        "+new one",
        "+new two",
        "@@ -9 +11 @@",
        "-old",
        "+changed",
    ])

    def test_parses_added_lines_per_file(self):
        self.assertEqual(lint.added_lines(self.DIFF), {"skills/demo/SKILL.md": {4, 5, 11}})

    def test_keeps_only_findings_on_added_lines(self):
        keep = {"file": "skills/demo/SKILL.md", "line": 5, "rule": "filler", "text": "a"}
        drop = {"file": "skills/demo/SKILL.md", "line": 6, "rule": "filler", "text": "b"}
        other = {"file": "skills/other/SKILL.md", "line": 5, "rule": "filler", "text": "c"}
        self.assertEqual(lint.in_diff([keep, drop, other], lint.added_lines(self.DIFF)), [keep])


class Fingerprint(unittest.TestCase):
    def test_survives_a_line_moving(self):
        a = {"file": "f", "rule": "r", "line": 1, "text": "same"}
        self.assertEqual(pr.fingerprint(a), pr.fingerprint(dict(a, line=99)))

    def test_changes_with_the_text(self):
        a = {"file": "f", "rule": "r", "line": 1, "text": "same"}
        self.assertNotEqual(pr.fingerprint(a), pr.fingerprint(dict(a, text="other")))


def thread(fp, resolved=False, author="github-actions[bot]", tid="T1"):
    return {"id": tid, "resolved": resolved, "author": author,
            "body": "x\n<!-- skill-lint:{} -->".format(fp), "path": "f", "line": 1}


class Sync(unittest.TestCase):
    F = {"file": "f", "rule": "r", "line": 1, "text": "t", "message": "m"}

    def test_posts_new_finding(self):
        post, resolve = pr.plan_sync([self.F], [])
        self.assertEqual((post, resolve), ([self.F], []))

    def test_does_not_repost_open_finding(self):
        post, resolve = pr.plan_sync([self.F], [thread(pr.fingerprint(self.F))])
        self.assertEqual((post, resolve), ([], []))

    def test_does_not_repost_finding_someone_resolved(self):
        post, _ = pr.plan_sync([self.F], [thread(pr.fingerprint(self.F), resolved=True)])
        self.assertEqual(post, [])

    def test_resolves_thread_when_finding_is_gone(self):
        post, resolve = pr.plan_sync([], [thread("abc")])
        self.assertEqual((post, resolve), ([], ["T1"]))

    def test_never_auto_resolves_a_human_or_reviewer_thread(self):
        reviewer = dict(thread("abc"), body="plain review comment")
        self.assertEqual(pr.plan_sync([], [reviewer]), ([], []))

    def test_an_untrusted_marker_cannot_get_its_thread_auto_resolved(self):
        self.assertEqual(pr.plan_sync([], [thread("abc", author="stranger")]), ([], []))


class Trust(unittest.TestCase):
    def test_bot_and_owner_are_trusted(self):
        self.assertTrue(pr.trusted("github-actions[bot]", "owner"))
        self.assertTrue(pr.trusted("owner", "owner"))

    def test_anyone_else_is_not(self):
        self.assertFalse(pr.trusted("stranger", "owner"))

    def test_splits_threads_by_trust_and_skips_resolved(self):
        threads = [thread("a", tid="1"), thread("b", resolved=True, tid="2"),
                   thread("c", author="stranger", tid="3")]
        fix, ignored = pr.open_threads(threads, "owner")
        self.assertEqual(([t["id"] for t in fix], [t["id"] for t in ignored]), (["1"], ["3"]))


class Quote(unittest.TestCase):
    TEXT = "one\nFix it as needed.\nthree\n"

    def test_accepts_a_quote_on_its_line(self):
        self.assertTrue(pr.quote_matches(self.TEXT, {"line": 2, "quote": "as needed"}))

    def test_rejects_a_made_up_quote(self):
        self.assertFalse(pr.quote_matches(self.TEXT, {"line": 2, "quote": "not here"}))

    def test_rejects_a_line_past_the_end_and_an_empty_quote(self):
        self.assertFalse(pr.quote_matches(self.TEXT, {"line": 99, "quote": "one"}))
        self.assertFalse(pr.quote_matches(self.TEXT, {"line": 2, "quote": ""}))


class Decide(unittest.TestCase):
    def test_fix_while_threads_are_open(self):
        self.assertEqual(pr.decide("success", 1, "h", "", 1), "FIX")

    def test_wait_for_ci_before_anything_else(self):
        self.assertEqual(pr.decide("pending", 1, "h", "", 1), "WAIT")

    def test_fix_when_ci_fails(self):
        self.assertEqual(pr.decide("failure", 0, "h", "", 1), "FIX")

    def test_review_when_this_head_has_no_clean_review(self):
        self.assertEqual(pr.decide("success", 0, "new", "old", 1), "REVIEW")

    def test_pass_needs_green_no_threads_and_clean_review_of_this_head(self):
        self.assertEqual(pr.decide("success", 0, "h", "h", 2), "PASS")

    def test_escalates_after_the_round_limit_unless_passing(self):
        self.assertEqual(pr.decide("success", 1, "h", "", pr.MAX_ROUNDS + 1), "ESCALATE")
        self.assertEqual(pr.decide("success", 0, "h", "h", pr.MAX_ROUNDS + 1), "PASS")


if __name__ == "__main__":
    unittest.main()
