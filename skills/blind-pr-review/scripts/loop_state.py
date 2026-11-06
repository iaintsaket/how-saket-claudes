#!/usr/bin/env python3
"""Decide the next step of the review loop, so the author can't declare victory.

    loop_state.py --state FILE record --head SHA --findings FINDINGS.json
    loop_state.py --state FILE dispute --fingerprint FP --reason "..."

Prints JSON. Exit codes: PASS 0, FIX 10, REVIEW 11, ESCALATE 20; 2 means bad usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

BLOCKING = {"Critical", "High", "Medium"}
MAX_ROUNDS = 5
CLEAN_ROUNDS = 2
EXIT = {"PASS": 0, "FIX": 10, "REVIEW": 11, "ESCALATE": 20}


def fingerprint(finding: dict) -> str:
    """Reviewers word things differently, so a finding is its file and its class of bug."""
    key = f"{finding.get('file')}|{finding.get('class')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def blockers(findings: list) -> list:
    return [f for f in findings if f.get("severity") in BLOCKING]


def lows(rounds: list) -> list:
    seen, out = set(), []
    for r in rounds:
        for f in r["findings"]:
            if f.get("severity") not in BLOCKING and fingerprint(f) not in seen:
                seen.add(fingerprint(f))
                out.append(f)
    return out


def clean_on_this_head(rounds: list) -> int:
    count = 0
    for r in reversed(rounds):
        if r["head"] != rounds[-1]["head"] or blockers(r["findings"]):
            break
        count += 1
    return count


def returned_after_fix(rounds: list) -> list:
    latest = rounds[-1]
    earlier = {fingerprint(f) for r in rounds[:-1] if r["head"] != latest["head"] for f in blockers(r["findings"])}
    return [f for f in blockers(latest["findings"]) if fingerprint(f) in earlier]


def decide(state: dict) -> dict:
    rounds = state["rounds"]
    out = {"round": len(rounds), "low": lows(rounds), "blocking": blockers(rounds[-1]["findings"])}
    if state["disputes"]:
        return {**out, "decision": "ESCALATE", "reason": "A finding is disputed; a human decides."}
    back = returned_after_fix(rounds)
    if back:
        return {**out, "decision": "ESCALATE", "reason": "A finding came back after its fix."}
    if clean_on_this_head(rounds) >= CLEAN_ROUNDS:
        reason = f"No findings in {CLEAN_ROUNDS} independent reviews of {rounds[-1]['head'][:10]}."
        return {**out, "decision": "PASS", "reason": reason}
    if len(rounds) >= MAX_ROUNDS:
        return {**out, "decision": "ESCALATE", "reason": f"Reached {MAX_ROUNDS} rounds."}
    if out["blocking"]:
        return {**out, "decision": "FIX", "reason": "Fix each blocking finding with a failing test first."}
    return {**out, "decision": "REVIEW", "reason": "Clean so far; run another fresh reviewer."}


def record(state: dict, head: str, findings: list) -> dict:
    state["rounds"].append({"head": head, "findings": findings})
    return decide(state)


def dispute(state: dict, print_: str, reason: str) -> None:
    state["disputes"].append({"fingerprint": print_, "reason": reason})


def load(path: Path) -> dict:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"rounds": [], "disputes": []}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--state", type=Path, required=True)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("record")
    r.add_argument("--head", required=True)
    r.add_argument("--findings", type=Path, required=True)
    d = sub.add_parser("dispute")
    d.add_argument("--fingerprint", required=True)
    d.add_argument("--reason", required=True)
    args = p.parse_args()

    state = load(args.state)
    if args.command == "record":
        findings = json.loads(args.findings.read_text(encoding="utf-8"))["findings"]
        result = record(state, args.head, findings)
    else:
        dispute(state, args.fingerprint, args.reason)
        result = {"decision": "ESCALATE", "reason": "A finding is disputed; a human decides."}
    args.state.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.state.write_text(json.dumps(state, indent=1), encoding="utf-8")
    print(json.dumps(result, indent=1))
    return EXIT[result["decision"]]


if __name__ == "__main__":
    sys.exit(main())
