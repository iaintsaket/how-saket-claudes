#!/usr/bin/env python3
"""Post skill findings on exact PR lines, and decide when the fix loop ends.

    pr_review.py sync --pr N --findings F.json        CI: mirror lint findings to the PR
    pr_review.py post --pr N --findings F.json        Reviewer: post checked findings
    pr_review.py status --pr N                        Print the next step
    pr_review.py record --pr N --findings-count N     Count a finished review round
    pr_review.py resolve --thread ID --reply TEXT     Reply to a fixed thread and close it

status exit codes: PASS 0, FIX 10, REVIEW 11, WAIT 12, ESCALATE 20.
PR comments are public input, so only the workflow bot and the repo owner are trusted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lint_skill import added_lines

MAX_ROUNDS = 5
MAX_COMMENTS = 30
BOTS = {"github-actions", "github-actions[bot]"}
LINT_MARK = re.compile(r"<!-- skill-lint:([0-9a-f]+) -->")
EXIT = {"PASS": 0, "FIX": 10, "REVIEW": 11, "WAIT": 12, "ESCALATE": 20}
THREADS = """
query($owner: String!, $name: String!, $pr: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100) {
        nodes {
          id isResolved path line
          comments(first: 1) { nodes { body author { login } } }
        }
      }
    }
  }
}
"""
RESOLVE = "mutation($id: ID!) { resolveReviewThread(input: {threadId: $id}) { thread { id } } }"
REPLY = """
mutation($id: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: {pullRequestReviewThreadId: $id, body: $body}) {
    comment { id }
  }
}
"""


def fingerprint(item):
    """A finding keeps its identity when other edits move its line."""
    key = "{}|{}|{}".format(item["file"], item["rule"], item["text"])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def trusted(author, owner):
    return author in BOTS or author == owner


def lint_mark(thread):
    if thread["author"] not in BOTS:
        return None
    match = LINT_MARK.search(thread["body"])
    return match.group(1) if match else None


def plan_sync(findings, threads):
    """Return (findings to post, thread ids to resolve)."""
    marked = {lint_mark(t): t for t in threads if lint_mark(t)}
    current = {fingerprint(f) for f in findings}
    post = [f for f in findings if fingerprint(f) not in marked]
    resolve = [t["id"] for mark, t in marked.items() if mark not in current and not t["resolved"]]
    return post, resolve


def open_threads(threads, owner):
    """Split unresolved threads into (to fix, ignored as untrusted)."""
    unresolved = [t for t in threads if not t["resolved"]]
    return ([t for t in unresolved if trusted(t["author"], owner)],
            [t for t in unresolved if not trusted(t["author"], owner)])


def quote_matches(text, item):
    """A reviewer's finding must quote the line it cites, so none can be invented."""
    lines = text.split("\n")
    line, quote = item.get("line", 0), item.get("quote", "")
    return bool(quote) and 1 <= line <= len(lines) and quote in lines[line - 1]


def decide(ci, open_count, head, clean_head, rounds):
    if ci == "pending":
        return "WAIT"
    if ci == "success" and open_count == 0 and head == clean_head:
        return "PASS"
    if rounds > MAX_ROUNDS:
        return "ESCALATE"
    if ci != "success" or open_count:
        return "FIX"
    return "REVIEW"


def gh(*args, stdin=None):
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True)
    if done.returncode:
        sys.exit("gh {} failed: {}".format(args[0], done.stderr.strip()))
    return done.stdout


def repo():
    data = json.loads(gh("repo", "view", "--json", "name,owner"))
    return data["owner"]["login"], data["name"]


def graphql(query, **fields):
    args = ["api", "graphql", "-f", "query=" + query]
    for key, value in fields.items():
        args += ["-F" if isinstance(value, int) else "-f", "{}={}".format(key, value)]
    return json.loads(gh(*args))["data"]


def fetch_threads(owner, name, pr):
    data = graphql(THREADS, owner=owner, name=name, pr=pr)
    threads = []
    for node in data["repository"]["pullRequest"]["reviewThreads"]["nodes"]:
        first = node["comments"]["nodes"][0]
        threads.append({"id": node["id"], "resolved": node["isResolved"], "path": node["path"],
                        "line": node["line"], "body": first["body"],
                        "author": (first["author"] or {}).get("login", "")})
    return threads


def head_of(pr):
    return json.loads(gh("pr", "view", str(pr), "--json", "headRefOid"))["headRefOid"]


def post_comments(owner, name, pr, comments, summary):
    payload = {"commit_id": head_of(pr), "event": "COMMENT", "body": summary,
               "comments": comments[:MAX_COMMENTS]}
    gh("api", "repos/{}/{}/pulls/{}/reviews".format(owner, name, pr), "--method", "POST",
       "--input", "-", stdin=json.dumps(payload))


def sync(args):
    findings = json.loads(Path(args.findings).read_text())
    owner, name = repo()
    post, resolve = plan_sync(findings, fetch_threads(owner, name, args.pr))
    if post:
        comments = [{"path": f["file"], "line": f["line"], "side": "RIGHT",
                     "body": "**{}**: {}\n\n<!-- skill-lint:{} -->".format(
                         f["rule"], f["message"], fingerprint(f))} for f in post]
        post_comments(owner, name, args.pr, comments, "skill-verifier found {} issue(s).".format(len(post)))
    for thread_id in resolve:
        graphql(RESOLVE, id=thread_id)
    print(json.dumps({"posted": len(post), "resolved": len(resolve), "open": len(findings)}))


def post(args):
    findings = json.loads(Path(args.findings).read_text())
    owner, name = repo()
    head = head_of(args.pr)
    added = added_lines(gh("pr", "diff", str(args.pr)))
    good, rejected = [], []
    for item in findings:
        shown = subprocess.run(["git", "show", "{}:{}".format(head, item.get("file"))],
                               capture_output=True, text=True)
        usable = (shown.returncode == 0 and quote_matches(shown.stdout, item)
                  and item["line"] in added.get(item["file"], set()))
        (good if usable else rejected).append(item)
    if good:
        comments = [{"path": f["file"], "line": f["line"], "side": "RIGHT",
                     "body": "**{}**: {}".format(f.get("rule", "review"), f.get("message", ""))} for f in good]
        post_comments(owner, name, args.pr, comments, "skill-verifier review: {} finding(s).".format(len(good)))
    print(json.dumps({"posted": len(good), "rejected": rejected}, indent=2))


def state_path(owner, name, pr):
    return Path.home() / ".claude" / "skill-verify" / "{}-{}-{}.json".format(owner, name, pr)


def read_state(path):
    return json.loads(path.read_text()) if path.exists() else {"rounds": 0, "clean_head": ""}


def ci_state(pr):
    done = subprocess.run(["gh", "pr", "checks", str(pr), "--json", "bucket"],
                          capture_output=True, text=True)
    buckets = {c["bucket"] for c in json.loads(done.stdout or "[]")}
    if not buckets or "pending" in buckets:
        return "pending"
    return "failure" if buckets & {"fail", "cancel"} else "success"


def status(args):
    owner, name = repo()
    state = read_state(state_path(owner, name, args.pr))
    fix, ignored = open_threads(fetch_threads(owner, name, args.pr), owner)
    head = head_of(args.pr)
    ci = ci_state(args.pr)
    action = decide(ci, len(fix), head, state["clean_head"], state["rounds"] + 1)
    print(json.dumps({"action": action, "ci": ci, "head": head, "rounds": state["rounds"],
                      "threads": fix, "ignored_untrusted": ignored}, indent=2))
    return EXIT[action]


def record(args):
    owner, name = repo()
    path = state_path(owner, name, args.pr)
    state = read_state(path)
    state["rounds"] += 1
    if args.findings_count == 0:
        state["clean_head"] = head_of(args.pr)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state))
    print(json.dumps(state))


def resolve(args):
    graphql(REPLY, id=args.thread, body=args.reply)
    graphql(RESOLVE, id=args.thread)
    print(json.dumps({"resolved": args.thread}))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for command, handler in (("sync", sync), ("post", post)):
        sub = commands.add_parser(command)
        sub.add_argument("--pr", type=int, required=True)
        sub.add_argument("--findings", required=True)
        sub.set_defaults(handler=handler)
    sub = commands.add_parser("status")
    sub.add_argument("--pr", type=int, required=True)
    sub.set_defaults(handler=status)
    sub = commands.add_parser("record")
    sub.add_argument("--pr", type=int, required=True)
    sub.add_argument("--findings-count", type=int, required=True)
    sub.set_defaults(handler=record)
    sub = commands.add_parser("resolve")
    sub.add_argument("--thread", required=True)
    sub.add_argument("--reply", required=True)
    sub.set_defaults(handler=resolve)
    args = parser.parse_args()
    return args.handler(args) or 0


if __name__ == "__main__":
    sys.exit(main())
