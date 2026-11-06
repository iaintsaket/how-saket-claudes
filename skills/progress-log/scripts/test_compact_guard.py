#!/usr/bin/env python3
"""Tests for compact_guard.py. Run: python3 test_compact_guard.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "compact_guard.py"


def remind(tokens, session):
    with tempfile.TemporaryDirectory() as folder:
        transcript = Path(folder) / "t.jsonl"
        transcript.write_text(json.dumps({
            "type": "assistant",
            "message": {"usage": {"input_tokens": tokens}},
        }) + "\n")
        hook = {"transcript_path": str(transcript), "session_id": session}
        done = subprocess.run([sys.executable, str(SCRIPT), "remind"],
                              input=json.dumps(hook), capture_output=True, text=True)
    return done.stdout


class Remind(unittest.TestCase):
    def test_quiet_below_the_threshold(self):
        self.assertEqual(remind(1000, "quiet"), "")

    def test_a_finished_group_is_a_compact_point(self):
        session = "group-{}".format(next(tempfile._get_candidate_names()))
        context = json.loads(remind(200000, session))["hookSpecificOutput"]["additionalContext"]
        self.assertIn("group of subtasks", context)
        self.assertIn("run /compact when the group finishes", context)


if __name__ == "__main__":
    unittest.main()
