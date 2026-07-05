#!/usr/bin/env python3
"""
build-events-sitemap.py - generate sitemap-events.xml with per-event URLs.

Purpose: every upcoming event has a server-rendered page at druk.se/e/<id>
(mc-og Cloudflare Worker). This sitemap tells crawlers those pages exist.
Referenced from robots.txt next to the main sitemap.xml. Runs automatically
via .github/workflows/build-og-data.yml.

Excludes canaries, ads/places and past events (past share links keep working
but are not advertised to crawlers).

Usage: python3 tools/build-events-sitemap.py
"""

import json
import os
from datetime import date
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://druk.se"


def load_events(filename):
    path = os.path.join(ROOT, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        s = f.read()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        return []
    return json.loads(s[start:end + 1]).get("events", [])


def main():
    today = date.today().isoformat()
    urls = []
    for ev in load_events("events.js"):
        if ev.get("_canary") or ev.get("_ad"):
            continue
        end = ev.get("dateEnd") or ev.get("date") or ""
        if not end or end < today:
            continue
        eid = ev.get("id")
        if not eid:
            continue
        urls.append((eid, ev.get("date") or today))

    urls.sort(key=lambda u: (u[1], u[0]))

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for eid, _d in urls:
        lines.append(
            f"    <url><loc>{SITE}/e/{escape(eid)}</loc>"
            f"<lastmod>{today}</lastmod><changefreq>weekly</changefreq>"
            f"<priority>0.6</priority></url>"
        )
    lines.append("</urlset>\n")

    dest = os.path.join(ROOT, "sitemap-events.xml")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Wrote {dest}: {len(urls)} event URLs")


if __name__ == "__main__":
    main()
