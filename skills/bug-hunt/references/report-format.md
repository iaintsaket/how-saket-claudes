# Report format and writing style

Read in Phase 9 before writing `report.md`.

## Writing style: plain and specific

Triage engineers read hundreds of reports a month and quickly dismiss padded, templated prose, even when the bug is real. Write the way a careful researcher explains a finding to a colleague: direct, specific and short. If the program requires disclosing AI assistance, disclose it. The PoC artifacts (`run-poc.sh`, the code) are exempt — only the prose (report.md, notes.md, H1 submission text) needs this treatment.

**Cut these AI tells:**

- **Em-dashes used as a stylistic crutch.** Claude reaches for `—` constantly. Most humans use commas, parentheses, or two sentences. Aim for ≤1 em-dash per ~500 words. If you find more, replace them.
- **Excessive triadic phrasing** ("real, exploitable, and adequately demonstrated"). Use two-item lists or single nouns where possible.
- **Generic AI vocabulary**: "leverage" (as verb), "robust", "comprehensive", "elegant", "seamless", "delve into", "navigate the complexities", "it's worth noting", "it's important to remember", "in essence", "fundamentally", "ultimately", "underscore", "showcase".
- **Section dividers (`---`) every other paragraph.** Use them only to separate genuinely top-level sections, not every block.
- **Emojis and decorative box characters** (✅ ❌ ⚠ ╔ ╠ ╚ etc.). Bug reports don't use these. Strip them all.
- **Tables for everything.** If three rows of a table can be three lines of prose, write prose.
- **"Bonus modifiers" / "Estimated bounty range" sections that read like a template.** Real reporters either omit these or write them in one line of prose.
- **Perfect parallelism in numbered lists.** Real human lists have variable sentence length, occasional fragments, and uneven punctuation.
- **Restating the title in the first sentence of the Summary.** Get to the substance immediately.
- **"This is the smoking gun" / "structurally undeniable" / "the strongest possible framing"**  — drop self-congratulatory framings entirely.
- **CVE-checklist boilerplate** ("CWE-345 (Insufficient Verification of Data Authenticity), CVSS 4.0 estimate: …"). Include CWE / CVSS only if you're confident; one line max, no parenthetical name expansions.

**Adopt these human habits:**

- Write in the first person ("I noticed", "I tested", "I couldn't reproduce") when describing investigation. Drop to passive only for the bug description itself.
- Vary sentence length deliberately. Mix one short sentence between two longer ones.
- Show command output without prefacing with "Here is the output". Just paste it.
- Be brief in the intro paragraph. Two or three sentences. Get to the code.
- For Steps to Reproduce, write the commands and what you observed — not the meta-narrative of running them.
- Skip the closing summary table / "submit first" ranking — these are workflow notes, not part of an H1 report.

**Before you save report.md, re-read it and run this checklist:**

1. Search for `—` — is the count under one per page?
2. Search for the AI vocabulary list — any hits? Replace.
3. Are there emojis or box-drawing chars? Strip.
4. Does the first sentence of any section restate its header? Rewrite.
5. Could any table be three lines of prose? Convert.
6. Does the report read like one human wrote it in one sitting, or like 40 LLM paragraphs glued together? If the latter, rewrite the connective tissue.

It's done when a triager could reproduce the bug from it in ten minutes without asking a question.

## Report content

Print a complete structured report. For each confirmed finding:

---

### [SEVERITY] — [Vulnerability Type]

**File:** `path/to/file.ts:LINE`
**CWE:** CWE-XXX ([name])
**CVSS 4.0 estimate:** X.X ([vector string])

**Summary:** One sentence — what the bug is and what an attacker can do with it.

**Affected version:** (from package.json / git tags)

**Attack prerequisites:** Unauthenticated / Authenticated as any user / Admin only

**Taint path:**
```
[user input source] → [function A] → [function B] → [dangerous sink]
```

**Steps to Reproduce:**
1. ...
2. ...
3. ...

**Proof of Concept:**
```
[minimal working exploit code or curl command]
```

**Impact:** Concretely, what can the attacker achieve? Data accessed? System compromised? Service disrupted?

**Suggested Fix:** What code change would remediate this?

**Bonus modifiers applicable:**
- [ ] +50% — affects multiple projects in the ecosystem
- [ ] +25% — patch suggestion included
- [ ] +25% — in a core security feature

**HackerOne Severity:** Low / Medium / High / Critical
**Estimated bounty:** $X – $Y (Tier X program rules)

---

After all findings, print the summary:

```
╔══════════════════════════════════════════╗
║           BUG HUNT SUMMARY               ║
╠══════════════════════════════════════════╣
║ Repo          : [name]                   ║
║ Hunt duration : [elapsed]                ║
║ Files scanned : [count]                  ║
╠══════════════════════════════════════════╣
║ FINDINGS                                 ║
║   Critical : [n]                         ║
║   High     : [n]                         ║
║   Medium   : [n]                         ║
║   Low      : [n]                         ║
║   Discarded: [n] (false positives)       ║
╠══════════════════════════════════════════╣
║ SUBMIT FIRST (ranked by severity+conf)   ║
║   1. [finding name] — $X–$Y             ║
║   2. [finding name] — $X–$Y             ║
║   3. [finding name] — $X–$Y             ║
╠══════════════════════════════════════════╣
║ Est. total bounty : $X – $Y              ║
╚══════════════════════════════════════════╝
```

Then give the user 3 concrete next steps: what to set up locally to validate the top finding, or what part of the code to dig deeper into if nothing confirmed was found.
