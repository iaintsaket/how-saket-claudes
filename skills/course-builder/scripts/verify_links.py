#!/usr/bin/env python3
"""Verify every link in a course file before publishing.

Usage: python3 verify_links.py <file.html|file.txt> [more files...]

- YouTube watch/playlist URLs are checked through YouTube's oEmbed endpoint
  (a 200 there means the video exists and is public); the title is printed so
  you can confirm it matches what the course says.
- Every other http(s) URL gets a GET with a browser User-Agent; 2xx/3xx = OK.
Exits non-zero if any link is broken, so a run doubles as a pre-publish gate.
"""
import json, re, sys, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
URL_RE = re.compile(r"https?://[^\s\"'<>`)\]]+")

def check(url):
    try:
        if "youtube.com/" in url or "youtu.be/" in url:
            api = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(url, safe="")
            with urllib.request.urlopen(urllib.request.Request(api, headers=UA), timeout=15) as r:
                d = json.load(r)
            return True, f"{d.get('title')} | {d.get('author_name')}"
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            return r.status < 400, str(r.status)
    except urllib.error.HTTPError as e:
        # Some sites block bots on GET but are fine; flag 403/429 as "check manually".
        return (None if e.code in (403, 429) else False), f"HTTP {e.code}"
    except Exception as e:
        return False, type(e).__name__

def main(paths):
    text = "".join(open(p, encoding="utf-8").read() for p in paths)
    # Resolve the template's string-concatenated prefixes, e.g. D+"concepts/" .
    consts = dict(re.findall(r'const\s+(\w+)\s*=\s*"(https?://[^"]+)"', text))
    for name, base in consts.items():
        text += "\n" + "\n".join(base + m for m in re.findall(rf'\b{name}\s*\+\s*"([^"]*)"', text))
    urls = sorted({u.rstrip(".,;") for u in URL_RE.findall(text)
                   if not re.search(r"fonts\.(googleapis|gstatic)\.com|cdnjs|jsdelivr|unpkg", u)
                   and u not in consts.values()})
    bad = 0
    with ThreadPoolExecutor(8) as ex:
        for url, (ok, info) in zip(urls, ex.map(check, urls)):
            tag = "OK  " if ok else ("WARN" if ok is None else "FAIL")
            bad += ok is False
            print(f"{tag} {url}  [{info}]")
    print(f"\n{len(urls)} links, {bad} broken")
    sys.exit(1 if bad else 0)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
