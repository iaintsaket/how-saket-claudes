"""Tests for token_audit.py. Run: python3 test_token_audit.py"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("token_audit.py")


def assistant(msg_id, ctx, blocks=(), ts="2026-11-01T10:00:00Z"):
    usage = {"input_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": ctx,
             "output_tokens": 10}
    return {"type": "assistant", "timestamp": ts,
            "message": {"id": msg_id, "usage": usage, "content": list(blocks)}}


def tool_use(tid, name, **inp):
    return {"type": "tool_use", "id": tid, "name": name, "input": inp}


def result(tid, content):
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": tid, "content": content}]}}


def prompt(text):
    return {"type": "user", "message": {"content": text}}


class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def session(self, name, entries, project="proj"):
        d = self.root / project
        d.mkdir(exist_ok=True)
        (d / f"{name}.jsonl").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    def run_audit(self, *args):
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--projects", str(self.root), "--format", "json", *args],
            capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_response_logged_on_several_lines_counts_once(self):
        self.session("s1", [
            prompt("hi"),
            assistant("m1", 1000), assistant("m1", 1000),  # one response, two lines
            assistant("m2", 3000),
        ])
        totals = self.run_audit()["totals"]
        self.assertEqual(totals["calls"], 2)
        self.assertEqual(totals["context_tokens"], 4000)
        self.assertEqual(totals["avg_context"], 2000)

    def test_sessions_rank_by_context_with_first_typed_prompt_and_tools(self):
        self.session("small", [prompt("small job"), assistant("a", 500)])
        self.session("big", [
            prompt("<command-name>/clear</command-name>"),  # not typed by the user
            prompt("refactor the whole billing module and all of its many tests please now"),
            assistant("b1", 9000, [tool_use("t1", "Bash", command="ls"),
                                   tool_use("t2", "Bash", command="pwd")]),
            assistant("b2", 9000, [tool_use("t3", "Read", file_path="/x.py")]),
        ])
        sessions = self.run_audit()["sessions"]
        self.assertEqual([s["session"] for s in sessions], ["big", "small"])
        self.assertEqual(sessions[0]["context_tokens"], 18000)
        self.assertEqual(sessions[0]["calls"], 2)
        self.assertEqual(sessions[0]["prompt"],
                         "refactor the whole billing module and all of its many tests…")
        self.assertEqual(sessions[0]["tools"], {"Bash": 2, "Read": 1})

    def test_tool_results_group_by_source_and_images_count_apart(self):
        self.session("s", [
            prompt("go"),
            assistant("m1", 100, [
                tool_use("t1", "Bash", command="cd /repo && python3 scripts/fetch_news.py --days 3"),
                tool_use("t2", "Bash", command="python3 scripts/fetch_news.py"),
                tool_use("t3", "mcp__canva__search-designs", query="x"),
                tool_use("t4", "Read", file_path="/tmp/shot.png"),
            ]),
            result("t1", "x" * 4000),
            result("t2", "x" * 400),
            result("t3", [{"type": "text", "text": "y" * 800}]),
            result("t4", [{"type": "image", "source": {"type": "base64", "data": "z" * 90000}}]),
        ])
        tools = {t["source"]: t for t in self.run_audit()["tools"]}
        self.assertEqual(tools["Bash: fetch_news.py"]["calls"], 2)
        self.assertEqual(tools["Bash: fetch_news.py"]["est_tokens"], 1100)  # 4,400 chars / 4
        self.assertEqual(tools["mcp: canva"]["est_tokens"], 200)
        self.assertEqual(tools["Read"]["est_tokens"], 0)  # base64 is not what an image costs
        self.assertEqual(tools["Read"]["images"], 1)
        self.assertEqual(next(iter(tools)), "Bash: fetch_news.py")  # largest first

    def test_a_file_read_three_times_in_one_session_is_flagged(self):
        reads = [tool_use(f"r{i}", "Read", file_path="/repo/big.py") for i in range(3)]
        twice = [tool_use(f"o{i}", "Read", file_path="/repo/small.py") for i in range(2)]
        self.session("s", [prompt("go"), assistant("m1", 100, reads + twice)]
                     + [result(f"r{i}", "a" * 800) for i in range(3)]
                     + [result(f"o{i}", "b" * 80) for i in range(2)])
        self.session("t", [prompt("go"), assistant("m2", 100, twice[:1])])  # other session
        self.assertEqual(self.run_audit()["rereads"], [
            {"session": "s", "file": "/repo/big.py", "reads": 3, "est_tokens": 600},
        ])

    def test_since_counts_only_activity_from_that_date(self):
        self.session("old", [prompt("old"), assistant("a", 1000, ts="2026-10-01T09:00:00Z")])
        self.session("mixed", [
            prompt("mixed"),
            assistant("b", 7000, ts="2026-10-31T23:59:59Z"),
            assistant("c", 500, ts="2026-11-01T00:00:00Z"),
        ])
        report = self.run_audit("--since", "2026-11-01")
        self.assertEqual(report["totals"], {"calls": 1, "context_tokens": 500, "avg_context": 500})
        self.assertEqual([s["session"] for s in report["sessions"]], ["mixed"])

    def test_since_refuses_a_date_it_cannot_read(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "--since", "last week"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("YYYY-MM-DD", done.stderr)

    def test_text_report_is_short_and_capped_by_top(self):
        for n, ctx in (("first", 9000), ("second", 5000), ("third", 1000)):
            self.session(n, [prompt(f"{n} task"), assistant(n, ctx)])
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--projects", str(self.root), "--top", "2"],
            capture_output=True, text=True,
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertIn("3 API calls, 15,000 context tokens, 5,000 per call on average", out)
        self.assertIn("first task", out)
        self.assertIn("second task", out)
        self.assertNotIn("third task", out)
        self.assertNotIn("{", out)  # not the JSON


if __name__ == "__main__":
    unittest.main()
