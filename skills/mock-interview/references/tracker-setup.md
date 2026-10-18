# Progress tracker setup (optional)

Each interview result is logged by `scripts/update-interview-tracker.sh`. Without setup, results go to `~/.claude/interview-tracker-local.jsonl`. To log them to a Google Sheet instead:

1. Create a Google Sheet, then open **Extensions → Apps Script**.
2. Paste in `assets/interview-tracker-apps-script.js` and save.
3. **Deploy → New deployment → Web app**. Set Execute as **Me** and access to **Anyone**, then deploy and copy the web app URL.
4. Create `~/.claude/interview-tracker-config.json` (it stays outside the repo and is never committed):

   ```json
   { "url": "https://script.google.com/macros/s/…/exec" }
   ```

5. Test it:

   ```bash
   bash scripts/update-interview-tracker.sh '{"date":"2026-01-01","mode":"DSA","questions":"test","score":5,"verdict":"No Hire","positives":"-","negatives":"-","topics_to_brush_up":"-"}'
   ```

The sheet gets one row per interview: date, mode, questions, score, verdict, what went well, what went wrong and topics to brush up.

Keep the web app URL private. Anyone who has it can append rows.
