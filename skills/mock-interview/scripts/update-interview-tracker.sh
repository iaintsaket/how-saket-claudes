#!/bin/bash
# Posts interview result JSON to the Google Apps Script web app.
# Usage: update-interview-tracker.sh '<json-string>'
# Falls back to a local JSONL log if the remote call fails.

CONFIG="$HOME/.claude/interview-tracker-config.json"
LOCAL_LOG="$HOME/.claude/interview-tracker-local.jsonl"

if [ ! -f "$CONFIG" ]; then
  echo "ERROR: Config not found at $CONFIG." >&2
  exit 1
fi

URL=$(python3 -c "import json; d=json.load(open('$CONFIG')); print(d['url'])" 2>/dev/null)
TOKEN=$(python3 -c "import json; d=json.load(open('$CONFIG')); print(d.get('token',''))" 2>/dev/null)

if [ -z "$URL" ] || [ "$URL" = "PASTE_YOUR_APPS_SCRIPT_URL_HERE" ]; then
  echo "ERROR: Apps Script URL not set in $CONFIG." >&2
  echo "$1" >> "$LOCAL_LOG"
  exit 0
fi

# Inject token into the payload
PAYLOAD=$(python3 -c "
import sys, json
d = json.loads(sys.argv[1])
d['token'] = sys.argv[2]
print(json.dumps(d))
" "$1" "$TOKEN" 2>/dev/null)

if [ -z "$PAYLOAD" ]; then
  echo "ERROR: Failed to build payload." >&2
  exit 1
fi

# Step 1: POST without following redirect — capture the Location header
REDIRECT_URL=$(curl -s -o /dev/null -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD" \
  --max-time 15 \
  -D - 2>&1 | grep -i "^location:" | tr -d '\r' | awk '{print $2}')

if [ -z "$REDIRECT_URL" ]; then
  echo "Remote update failed (no redirect from Apps Script). Saving to local log." >&2
  echo "$1" >> "$LOCAL_LOG"
  echo "Saved to local log: $LOCAL_LOG"
  exit 1
fi

# Step 2: Follow the redirect to get the JSON response
RESPONSE=$(curl -s "$REDIRECT_URL" --max-time 15 2>&1)

if echo "$RESPONSE" | grep -q '"status":"success"'; then
  ROW=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('row','?'))" 2>/dev/null)
  echo "Google Sheet updated successfully (row $ROW)."
elif echo "$RESPONSE" | grep -q '"status":"unauthorized"'; then
  echo "ERROR: Token rejected by Apps Script. Check token in $CONFIG." >&2
  exit 1
else
  echo "Remote update failed. Saving to local log." >&2
  echo "$1" >> "$LOCAL_LOG"
  echo "Saved to local log: $LOCAL_LOG"
fi
