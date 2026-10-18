---
name: course-builder
description: Build a compact, self-paced course on any tech topic. It researches the web, then publishes one interactive HTML page with modules, short notes, verified docs, blogs and YouTube videos, a hands-on task, and a quiz after every module. Use when the user says "create a course on X", "make me a course on X", "build a course for X", "learning path for X", "teach me X as a course", or "create this course". Not for quizzing someone in chat or for tutoring over many sessions.
license: MIT
compatibility: Needs web search and python3. Publishes with the Claude Code Artifact tool, or else writes a local HTML file.
metadata:
  author: iaintsaket
  version: "1.1.0"
---

# Course Builder

Make a tight, high-signal course the user can actually finish. Research first, then publish one interactive HTML page. Every link must be real.

The user wants a finished course, not a conversation. Don't ask questions unless the topic name itself is ambiguous (for example, "Pulsar" could be Apache Pulsar or something else). If the request names a goal or level ("for interview prep", "I know Kafka already"), shape the course to it. Otherwise assume a working engineer who is new to the topic and wants to use it in production. State the assumption in the page header.

## 1. Scope

- **6–8 modules, ordered by dependency.** Never use a concept before the module that teaches it. The usual arc is: why it exists → core concepts → architecture/internals → hands-on setup → developer APIs → advanced features → production/operations → how it compares to alternatives. Drop or merge stages that don't fit the topic.
- **Frame each module around a question.** Write an `aim` like "What happens to data when a broker dies?", not "Brokers". Add one `why` line on why a practitioner should care.
- **Per module:**
  - 4–6 bullets of notes, using the real terms of art in bold.
  - At most one code snippet or diagram, only where it shows the mechanism.
  - A 10–20 minute **Try it** task with a checkable outcome.
  - 2–4 readings and 1–2 videos.
  - 4 quiz questions.
- **End with a capstone:** one project of 3–5 concrete steps that exercises most modules.
- **Brevity budget:** notes stay around 150–250 words per module. If a module grows past that, move the depth into a reading link. A good course is about 8–10 hours of learning including the reading.

## 2. Research

Run searches in parallel batches. Use WebSearch in `standard` mode, and switch to `extended` when results are thin, such as for YouTube.

1. **Current state:** find the latest stable version and release notes. Check the official docs' own install page for the current version tag. Don't trust aggregator sites for this.
2. **Official docs:** concepts, architecture, getting started, and admin/ops pages. Link the stable docs path, not `/next/` or a pinned old version.
3. **Blogs:** vendor engineering blogs, company engineering blogs and well-known practitioners, preferring posts from the last ~3 years. Each reading must add something the others don't. Don't include five posts that say the same thing.
4. **YouTube:** query `youtube <topic> <subtopic>` and use official channels, conference talks (ASF, the project's summit, vendor channels) and well-known educators. Copy the exact `watch?v=` or `playlist?list=` URL from the results.
5. **Comparisons:** "X vs Y" posts for the positioning module. Label vendor-written comparisons as such in the `source` field.

**Never invent a link.** A made-up citation is the worst mistake this skill can make. Only use URLs that came from search results or a page you fetched. If a module has no verified video, leave `watch` empty rather than guessing.

## 3. Write the modules

Write the modules one at a time and give each one equal care. The last modules tend to get thin when everything is written in one pass. Check the facts you state against the docs you're linking.

### Quiz design (this matters most)

- Test **application, not recall**. Each question should be a small new scenario the notes didn't use, such as "Your consumers fall behind. Which metric shows it?". Avoid "What does X stand for?" and anything that can be answered by scrolling up and copying.
- Mix question types across the course: **apply to a new case**, **explain the why**, **predict what happens if…**, **choose between options or trade-offs**, and **debug a symptom**.
- Give four options, with exactly one clearly correct. Each wrong option should be a **real misconception**, not filler. Never use "all of the above".
- **Spread the correct answer position across 0–3.** In each quiz, no position should be correct more than twice.
- The explanation teaches. It says why the answer is right and what misconception the tempting wrong answer reflects. Keep the tone encouraging.

## 4. Build the page

1. Copy `assets/course-template.html` (next to this file) into the scratchpad dir as `<topic-slug>-course.html`.
2. Fill in the placeholders and the `MODULES` array. The field contract is documented in the template's comment. Replace the `{{topic-slug}}` storage key.
3. Make it look like the subject without rebuilding the page. Retune `--accent`/`--beam` and swap the single ornament SVG for something that fits the subject. Keep the token structure, both dark-mode blocks and the render script.
4. Run `grep -n '{{' <file>`. It must print nothing.
5. **Verify every link:** `python3 <skill-dir>/scripts/verify_links.py <file>`. It checks YouTube links through oEmbed (and prints titles, so you can confirm each title matches the module) and checks every other URL by HTTP. Replace or drop every `FAIL`. Check `WARN` (403/429) links by hand or drop them. Re-run until it shows 0 broken.
6. Check the JS once with `node --check` on the extracted script, if node is available.
7. Publish with the Artifact tool (icon `book`) and a one-sentence description. If there's no Artifact tool, save the HTML file and give its path.

## 5. Pre-publish checklist

- [ ] Modules are in dependency order, and each has an aim, a why, notes, a Try it task, readings and a quiz
- [ ] No wall of text: a visual break (a list, code, a callout or a link list) at least every 3 sentences
- [ ] Version facts match the current official docs, and the date is stated in the header
- [ ] Quiz answers are spread across positions, and every question is a scenario
- [ ] `verify_links.py` reports 0 broken, and the YouTube titles match their modules
- [ ] No `{{` placeholders left

## 6. Reply

Give the artifact link and a one-line-per-module outline. Mention anything you couldn't verify, such as a module with no video. Keep the reply short.
