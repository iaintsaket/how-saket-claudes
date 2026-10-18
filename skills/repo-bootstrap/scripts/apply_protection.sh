#!/usr/bin/env bash
# Protect a repo's default branch with the ruleset in assets/ruleset.json and apply
# hardening settings. Idempotent: re-running updates the existing ruleset in place.
# Usage: apply_protection.sh <owner/repo> [required-check ...]   (default check: ci)
set -euo pipefail

repo="${1:?usage: apply_protection.sh <owner/repo> [required-check ...]}"
shift
checks=("${@:-ci}")
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
template="$here/../assets/ruleset.json"
name="protect-default-branch"

body="$(python3 - "$template" "${checks[@]}" <<'PY'
import json, sys
rs = json.load(open(sys.argv[1]))
for rule in rs["rules"]:
    if rule["type"] == "required_status_checks":
        # 15368 = the GitHub Actions app, so only Actions can satisfy the check
        rule["parameters"]["required_status_checks"] = [
            {"context": c, "integration_id": 15368} for c in sys.argv[2:]
        ]
print(json.dumps(rs))
PY
)"

existing="$(gh api "repos/$repo/rulesets" --jq ".[] | select(.name==\"$name\") | .id" 2>/dev/null || true)"
if [ -n "$existing" ]; then
  method=PUT; path="repos/$repo/rulesets/$existing"
else
  method=POST; path="repos/$repo/rulesets"
fi

if ! out="$(printf '%s' "$body" | gh api -X "$method" "$path" --input - 2>&1)"; then
  echo "ERROR: could not apply ruleset to $repo:" >&2
  echo "$out" >&2
  if printf '%s' "$out" | grep -qiE 'upgrade|GitHub Pro|not available|403'; then
    echo "Rulesets on private repos need a paid plan. Make the repo public or upgrade." >&2
  fi
  exit 1
fi
echo "ruleset '$name' applied ($method) with required checks: ${checks[*]}"

gh repo edit "$repo" --delete-branch-on-merge --allow-update-branch >/dev/null \
  && echo "repo settings: delete-branch-on-merge, allow-update-branch"

if gh api -X PATCH "repos/$repo" --input - >/dev/null 2>&1 <<'JSON'
{"security_and_analysis": {"secret_scanning": {"status": "enabled"},
                           "secret_scanning_push_protection": {"status": "enabled"}}}
JSON
then
  echo "secret scanning + push protection: enabled"
else
  echo "WARN: secret scanning not enabled (needs a public repo or GitHub Advanced Security)" >&2
fi
