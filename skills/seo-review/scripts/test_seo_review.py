#!/usr/bin/env python3
"""Tests for seo_review.py. Run: python3 test_seo_review.py"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import seo_review as sr

SCRIPT = Path(__file__).parent / "seo_review.py"


def run(*args, stdin=""):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin, capture_output=True, text=True)


class Scope(unittest.TestCase):
    def test_keeps_pages_head_and_crawl_files_and_drops_tests_and_plumbing(self):
        changed = [
            "src/app/about/page.tsx", "src/app/layout.tsx", "pages/blog/[slug].jsx", "src/routes/+page.svelte",
            "content/posts/hello.md", "public/robots.txt", "src/app/sitemap.ts", "public/_redirects",
            "next.config.ts", "src/lib/seo.ts", "index.html",
            "src/app/seo.test.tsx", "e2e/layout.spec.ts", "src/api/client.ts", "README.md", "package-lock.json",
        ]
        self.assertEqual(sr.relevant(changed), changed[:11])

    def test_a_file_outside_page_paths_counts_when_its_added_lines_touch_seo(self):
        diff = "\n".join([
            "diff --git a/src/lib/copy.ts b/src/lib/copy.ts", "--- a/src/lib/copy.ts", "+++ b/src/lib/copy.ts", "@@ -1 +1 @@",
            "-  return `${name} options`;", "+  return { title: `${name}: from ${price}`, description };",
            "diff --git a/src/api/client.ts b/src/api/client.ts", "--- a/src/api/client.ts", "+++ b/src/api/client.ts", "@@ -1 +1 @@",
            "+  const res = await fetch(url);",
            "diff --git a/src/app/x.test.tsx b/src/app/x.test.tsx", "--- a/src/app/x.test.tsx", "+++ b/src/app/x.test.tsx", "@@ -1 +1 @@",
            "+  expect(meta.title).toBe(\"X\");",
            "diff --git a/src/app/about/page.tsx b/src/app/about/page.tsx", "--- a/src/app/about/page.tsx", "+++ b/src/app/about/page.tsx", "@@ -1 +1 @@",
            "+  return <p>hi</p>;",
        ])
        self.assertEqual(sr.relevant_in_diff(diff), ["src/lib/copy.ts", "src/app/about/page.tsx"])

    def test_cli_reads_a_diff_and_exits_1_when_nothing_is_relevant(self):
        plumbing = "diff --git a/README.md b/README.md\n--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n+the title of this repo\n"
        done = run("scope", stdin=plumbing)
        self.assertEqual((done.returncode, done.stdout.strip()), (1, "no SEO-relevant change"))
        page = "diff --git a/src/app/about/page.tsx b/src/app/about/page.tsx\n+++ b/src/app/about/page.tsx\n@@ -1 +1 @@\n+x\n"
        done = run("scope", stdin=page)
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "src/app/about/page.tsx"))


def finding(**changes):
    base = {"file": "app/page.tsx", "line": 2, "quote": 'title: "About"', "class": "intent", "severity": "should-fix",
            "impact": "The title names no topic, so the page cannot rank for what it covers.",
            "change": 'Use "About Acme: compare widget prices".'}
    base.update(changes)
    return base


class Check(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "app").mkdir()
        (self.root / "app/page.tsx").write_text('export const metadata = {\n  title: "About",\n};\n')
        (self.root.parent / "secret.txt").write_text("title: \"About\"\n")

    def check(self, items):
        return sr.check(items, self.root)

    def test_accepts_a_quoted_finding_and_rejects_each_broken_contract(self):
        accepted, rejected = self.check([
            finding(severity="consider"),
            finding(),
            finding(line=1),
            finding(file="../secret.txt", line=1),
            finding(**{"class": "style"}),
            finding(impact=" "),
        ])
        self.assertEqual([f["severity"] for f in accepted], ["should-fix", "consider"])
        self.assertEqual([r["reason"] for r in rejected], [
            "quote is not on line 1 of app/page.tsx",
            "file ../secret.txt is not in the checkout",
            "class must be one of: content, crawl, intent, links, performance, sharing, structured-data",
            "impact is required: say what search or sharing loses, and what to change",
        ])

    def test_cli_prints_json_and_exits_1_when_any_finding_is_rejected(self):
        path = self.root / "f.json"
        path.write_text(json.dumps([finding(), finding(line=3)]))
        done = run("check", "--findings", str(path), "--root", str(self.root))
        out = json.loads(done.stdout)
        self.assertEqual((done.returncode, len(out["accepted"]), len(out["rejected"])), (1, 1, 1))


if __name__ == "__main__":
    unittest.main()
