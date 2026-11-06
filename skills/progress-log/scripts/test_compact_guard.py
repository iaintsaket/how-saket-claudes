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


def run(mode, hook, home):
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home)}
    done = subprocess.run([sys.executable, str(SCRIPT), mode], input=json.dumps(hook),
                          capture_output=True, text=True, env=env)
    return done.stdout


def log_for(home, session):
    return Path(home) / ".claude" / "progress" / (session + ".md")


class Locate(unittest.TestCase):
    def test_tells_each_session_its_own_log_path(self):
        with tempfile.TemporaryDirectory() as home:
            out = json.loads(run("locate", {"session_id": "abc-123"}, home))
            context = out["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "SessionStart")
            self.assertIn(str(log_for(home, "abc-123")), context)

    def test_two_sessions_get_different_paths(self):
        with tempfile.TemporaryDirectory() as home:
            a = run("locate", {"session_id": "one"}, home)
            b = run("locate", {"session_id": "two"}, home)
            self.assertNotEqual(a, b)

    def test_an_id_cannot_escape_the_progress_folder(self):
        with tempfile.TemporaryDirectory() as home:
            context = json.loads(run("locate", {"session_id": "../../evil"}, home))[
                "hookSpecificOutput"]["additionalContext"]
            self.assertIn(str(log_for(home, "evil")), context)
            self.assertNotIn("..", context)

    def test_silent_without_a_session_id(self):
        with tempfile.TemporaryDirectory() as home:
            self.assertEqual(run("locate", {}, home), "")


class Restore(unittest.TestCase):
    def test_restores_this_sessions_log_not_the_projects_progress_md(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as project:
            (Path(project) / ".git").mkdir()
            (Path(project) / "progress.md").write_text("OTHER CHATS LOG")
            log = log_for(home, "mine")
            log.parent.mkdir(parents=True)
            log.write_text("MY OWN LOG")
            out = run("restore", {"session_id": "mine", "cwd": project}, home)
            self.assertIn("MY OWN LOG", out)
            self.assertNotIn("OTHER CHATS LOG", out)

    def test_nothing_to_restore_when_this_session_has_no_log(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as project:
            (Path(project) / "progress.md").write_text("OTHER CHATS LOG")
            self.assertEqual(run("restore", {"session_id": "fresh", "cwd": project}, home), "")


if __name__ == "__main__":
    unittest.main()
