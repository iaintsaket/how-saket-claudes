---
name: test-first
description: >-
  Builds a change one assertion at a time: state a testable claim, watch a test fail for the
  expected reason, write the smallest code that passes, then validate it on the real system,
  with script-checked proof of the order. Use when implementing a feature or fix from an approved
  plan, when the user says "TDD", "test first", "red green" or "/test-first", or when fixing a
  security finding. Not for docs, generated code, or research.
license: MIT
compatibility: Needs git and Python 3.9+.
metadata:
  author: iaintsaket
  version: "1.0.0"
---

# Test First

Move from assertion to validation, never from code to hope. Each change starts as a claim that can be false, and ends with evidence that it's true. Good output has a failing test that was seen to fail, and proof a reader can re-run.

This follows AI-DLC's Construction phase, with test-first as the test ordering: the approved plan is the Inception output, and each assertion is a small bolt. Inside each bolt the agent runs a ReAct loop: reason, act, observe. Observation means real output. An expected result is not an observation.

## Inputs

`$ARGUMENTS` / the request:
- A plan or a list of assertions → use them in order.
- A finding from `blind-pr-review` → the assertion is that the attack is refused.
- Neither → derive assertions from the request, and get approval before building, using the session's normal plan flow.

## Workflow

Run one bolt per assertion. Read `references/assertions.md` before writing the first one.

1. **Reason.** Write one assertion in the ledger: a single claim that can be false. For a security change, state what must be refused as well as what must work.
2. **Act: write the test.** Add only test code, then commit it alone. This commit is the red commit.
3. **Observe: confirm red.** Run the test. It must fail for the expected reason, not from a typo, import error or broken setup. Otherwise fix the test and repeat.
4. **Act: write the code.** Add the smallest change that passes. Leave the test alone, and commit. This commit is the green commit.
5. **Observe: confirm green.** Run the test, then the full suite and linters. Fix anything you broke.
6. **Refactor.** Clean up with the tests green, in a separate commit.
7. **Validate.** Prove the order:
   ```bash
   python3 scripts/verify_red_green.py --red RED_SHA --green GREEN_SHA --expect 'REGEX' -- TEST_COMMAND
   ```
   Then exercise the real thing wherever a unit test mocks the part that matters, such as a real CLI run, and record the output.
8. **Record.** Add the commits and the evidence to the ledger, then start the next bolt.

## Output

The ledger goes in the PR description, with a row per assertion. Reply with assertions proven, anything left unproven and why.

## Rules

- No production code without a test seen failing first. If code came first, set it aside and write the test from the assertion.
- Don't weaken a test to pass. `verify_red_green.py` rejects any test that changed between red and green.
- A test that can't fail proves nothing. If you can't make it fail, the assertion is wrong or already true, so say which.
- Stop and tell the user if an assertion turns out to need a plan change.
- Exceptions: docs, generated code, and configuration that has its own check. Name the exception in the ledger.
- Never claim "secure" or "bug-free". Report which assertions were proven.
- Python projects installed in editable mode import the main checkout, not the clean one: pass `env PYTHONPATH=src pytest …` so the check tests the right commit.

## Files

- `references/assertions.md`: read before the first bolt. Holds the ledger format and how to write strong assertions.
- `scripts/verify_red_green.py`: run at step 7. Exit 0 means proven and 1 means rejected.
- `scripts/test_verify_red_green.py`: the script's own tests.
