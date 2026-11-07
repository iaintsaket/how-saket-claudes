#!/usr/bin/env python3
"""Tests for check_findings.py. Run: python3 test_check_findings.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import check_findings as cf

SCRIPT = Path(__file__).parent / "check_findings.py"

DIFF = "\n".join([
    "diff --git a/app/cache.py b/app/cache.py",
    "--- a/app/cache.py",
    "+++ b/app/cache.py",
    "@@ -3,0 +4,2 @@ def get():",
    "+    CACHE[key] = value",
    "+    return value",
    "@@ -20 +22 @@",
    "-    old()",
    "+    new_call()",
])

PLAN = "# Plan\n\nAdd a cache in front of the database.\nNo eviction is planned.\n"


def finding(**changes):
    base = {"file": "app/cache.py", "line": 4, "quote": "CACHE[key] = value", "class": "risk",
            "severity": "block", "scenario": "The dict grows forever, so memory runs out after a day.",
            "change": "Use an LRU with a size limit."}
    base.update(changes)
    return base


class AddedLines(unittest.TestCase):
    def test_maps_each_file_to_the_lines_the_diff_adds(self):
        self.assertEqual(cf.added_lines(DIFF), {"app/cache.py": {4, 5, 22}})


class DiffMode(unittest.TestCase):
    def check(self, item):
        return cf.check([item], cf.Source.from_diff(DIFF, {"app/cache.py": "a\nb\nc\n    CACHE[key] = value\n    return value\n"}))

    def test_accepts_a_quote_on_an_added_line(self):
        accepted, rejected = self.check(finding())
        self.assertEqual((len(accepted), rejected), (1, []))

    def test_rejects_a_quote_that_is_not_on_the_line(self):
        _, rejected = self.check(finding(quote="something invented here"))
        self.assertIn("quote", rejected[0]["reason"])

    def test_rejects_a_line_the_diff_did_not_add(self):
        text = "\n".join(["x"] * 3 + ["    CACHE[key] = value"] + ["y"] * 30)
        _, rejected = cf.check([finding(line=1, quote="x")], cf.Source.from_diff(DIFF, {"app/cache.py": text}))
        self.assertIn("not added", rejected[0]["reason"])


class FileMode(unittest.TestCase):
    def test_any_line_of_a_plan_can_be_cited(self):
        item = finding(file="plan.md", line=4, quote="No eviction is planned.", **{"class": "wrong-problem"})
        accepted, rejected = cf.check([item], cf.Source.from_file("plan.md", PLAN))
        self.assertEqual((len(accepted), rejected), (1, []))


    def test_rejects_a_finding_that_cites_another_file(self):
        item = finding(file="other.md", line=4, quote="No eviction")
        _, rejected = cf.check([item], cf.Source.from_file("plan.md", PLAN))
        self.assertIn("file", rejected[0]["reason"])


class Contract(unittest.TestCase):
    def reject_reason(self, **changes):
        text = "a\nb\nc\n    CACHE[key] = value\n"
        _, rejected = cf.check([finding(**changes)], cf.Source.from_diff(DIFF, {"app/cache.py": text}))
        return rejected[0]["reason"] if rejected else None

    def test_rejects_an_unknown_class(self):
        self.assertIn("class", self.reject_reason(**{"class": "style"}))

    def test_rejects_an_unknown_severity(self):
        self.assertIn("severity", self.reject_reason(severity="nit"))

    def test_rejects_a_finding_with_no_failure_scenario(self):
        self.assertIn("scenario", self.reject_reason(scenario="  "))

    def test_rejects_a_finding_with_no_proposed_change(self):
        self.assertIn("change", self.reject_reason(change=""))

    def test_rejects_a_finding_that_is_not_an_object(self):
        _, rejected = cf.check(["text"], cf.Source.from_file("plan.md", PLAN))
        self.assertEqual(len(rejected), 1)


class Order(unittest.TestCase):
    def test_blocking_findings_come_first(self):
        source = cf.Source.from_file("plan.md", PLAN)
        later = finding(file="plan.md", line=3, quote="Add a cache", severity="consider")
        first = finding(file="plan.md", line=4, quote="No eviction", severity="block")
        accepted, _ = cf.check([later, first], source)
        self.assertEqual([f["severity"] for f in accepted], ["block", "consider"])


class Cli(unittest.TestCase):
    def run_cli(self, findings, *extra):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "findings.json"
            path.write_text(json.dumps(findings))
            plan = Path(folder) / "plan.md"
            plan.write_text(PLAN)
            done = subprocess.run([sys.executable, str(SCRIPT), "--findings", str(path),
                                   "--file", str(plan), *extra], capture_output=True, text=True)
        return done

    def test_exits_zero_and_prints_accepted_when_all_pass(self):
        item = finding(file="plan.md", line=4, quote="No eviction")
        done = self.run_cli([item])
        done_json = json.loads(done.stdout)
        self.assertEqual((done.returncode, len(done_json["accepted"])), (0, 1))

    def test_exits_one_when_any_finding_is_rejected(self):
        done = self.run_cli([finding(file="plan.md", line=4, quote="not in the plan")])
        self.assertEqual(done.returncode, 1)
        self.assertEqual(len(json.loads(done.stdout)["rejected"]), 1)

    def test_diff_mode_reads_the_files_from_the_checkout(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "app").mkdir()
            (root / "app" / "cache.py").write_text("a\nb\nc\n    CACHE[key] = value\n    return value\n")
            (root / "change.diff").write_text(DIFF)
            (root / "findings.json").write_text(json.dumps([finding()]))
            done = subprocess.run([sys.executable, str(SCRIPT), "--findings", str(root / "findings.json"),
                                   "--diff", str(root / "change.diff"), "--root", str(root)],
                                  capture_output=True, text=True)
        self.assertEqual((done.returncode, len(json.loads(done.stdout)["accepted"])), (0, 1))


if __name__ == "__main__":
    unittest.main()
