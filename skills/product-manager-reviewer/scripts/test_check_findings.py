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

PLAN = "# Plan\n\nBuild a habit app for everyone.\nUsers will love streaks.\nLaunch in March.\n"


def finding(**changes):
    base = {"file": "plan.md", "line": 3, "quote": "habit app for everyone", "class": "problem",
            "severity": "block",
            "assumption": "Everyone has a habit they want help with.",
            "test": "Ask 10 people in the target group what they tried last month to keep a habit.",
            "pivot": "Pick one group with a deadline, such as exam students, and build for them."}
    base.update(changes)
    return base


def check(*items):
    return cf.check(list(items), cf.Source("plan.md", PLAN))


class Accepts(unittest.TestCase):
    def test_accepts_a_quote_on_the_cited_line(self):
        accepted, rejected = check(finding())
        self.assertEqual((len(accepted), rejected), (1, []))

    def test_a_finding_below_block_needs_no_pivot(self):
        item = finding(severity="should-fix", line=4, quote="Users will love streaks")
        item.pop("pivot")
        accepted, rejected = check(item)
        self.assertEqual((len(accepted), rejected), (1, []))

    def test_no_findings_is_a_clean_review(self):
        self.assertEqual(check(), ([], []))


class Market(unittest.TestCase):
    def test_accepts_a_market_finding_about_price_and_payment(self):
        item = finding(severity="should-fix", line=4, quote="Users will love streaks",
                       assumption="The target group pays a monthly fee for habit tracking.",
                       test="Ask 10 people in the target group what they paid for apps last month.",
                       **{"class": "market"})
        accepted, rejected = check(item)
        self.assertEqual((len(accepted), rejected), (1, []))


class Rejects(unittest.TestCase):
    def reason(self, **changes):
        _, rejected = check(finding(**changes))
        return rejected[0]["reason"] if rejected else None

    def test_a_quote_that_is_not_on_the_line(self):
        self.assertIn("quote", self.reason(quote="a market of ten million"))

    def test_a_line_number_past_the_end(self):
        self.assertIn("quote", self.reason(line=99))

    def test_a_file_other_than_the_reviewed_one(self):
        self.assertIn("file", self.reason(file="other.md"))

    def test_an_unknown_class(self):
        self.assertIn("class", self.reason(**{"class": "style"}))

    def test_an_unknown_severity(self):
        self.assertIn("severity", self.reason(severity="nit"))

    def test_a_finding_that_names_no_assumption(self):
        self.assertIn("assumption", self.reason(assumption=" "))

    def test_a_finding_with_no_way_to_test_it(self):
        self.assertIn("test", self.reason(test=""))

    def test_a_block_with_no_pivot(self):
        self.assertIn("pivot", self.reason(pivot=""))

    def test_a_finding_that_is_not_an_object(self):
        _, rejected = check("text")
        self.assertEqual(len(rejected), 1)


class Order(unittest.TestCase):
    def test_blocking_findings_come_first(self):
        later = finding(severity="consider", line=4, quote="Users will love streaks")
        accepted, _ = check(later, finding())
        self.assertEqual([f["severity"] for f in accepted], ["block", "consider"])


class Cli(unittest.TestCase):
    def run_cli(self, findings):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "findings.json").write_text(json.dumps(findings))
            (Path(folder) / "plan.md").write_text(PLAN)
            return subprocess.run([sys.executable, str(SCRIPT), "--findings", str(Path(folder) / "findings.json"),
                                   "--file", str(Path(folder) / "plan.md")], capture_output=True, text=True)

    def test_exits_zero_and_prints_accepted_when_all_pass(self):
        done = self.run_cli([finding()])
        self.assertEqual((done.returncode, len(json.loads(done.stdout)["accepted"])), (0, 1))

    def test_exits_one_when_any_finding_is_rejected(self):
        done = self.run_cli([finding(quote="not in the plan at all")])
        self.assertEqual((done.returncode, len(json.loads(done.stdout)["rejected"])), (1, 1))


if __name__ == "__main__":
    unittest.main()
