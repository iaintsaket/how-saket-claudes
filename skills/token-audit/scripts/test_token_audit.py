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


if __name__ == "__main__":
    unittest.main()
