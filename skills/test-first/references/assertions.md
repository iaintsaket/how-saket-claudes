# Writing assertions

## Ledger format

Keep one table in the PR description.

```markdown
| # | Assertion | Red | Green | Failed with | Validated by |
|---|---|---|---|---|---|
| 1 | The upload refuses a path outside the data folder | abc123 | def456 | `AssertionError: 200 != 403` | Real request refused, 403 |
```

Use `n/a (reason)` when a step truly doesn't apply. A blank cell means unfinished.

## A strong assertion

- **One claim.** "It validates input and logs errors" is two bolts.
- **Falsifiable.** Name the input and the observable result.
- **About behaviour.** Assert what a caller sees, not private details, so refactoring doesn't break it.
- **Specific about failure.** Decide what the failure message should look like before running, and pass it to `--expect`.

| Weak | Strong |
|---|---|
| Handles bad input | A symbol containing `/` returns 400 and reads no file |
| Login is secure | A request without the key returns 403 and starts nothing |

## Security assertions

Prove the attack fails, then prove the normal path still works. A fix that blocks everything also passes a refusal test.

- **Refusal:** the hostile input is refused, and the side effect did not happen. Check the side effect itself, such as no file written or no process started.
- **Boundary:** test each side of a limit, including the value just past it.
- **Default:** the unsafe option is off unless someone turns it on.
- **Allowlist over blocklist:** assert the exact allowed set, so adding to it fails a test.
- **Real system:** a mock can only repeat your assumptions. When safety depends on another tool's behaviour, run that tool.

## Gotchas

- A test that errors during collection hasn't failed for the right reason.
- A test that fails on any exception can stay green for the wrong reason. Assert the specific result.
- Shared mocks can hide the failure. Check that the code path actually ran.
