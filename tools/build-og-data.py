#!/usr/bin/env python3
"""
build-og-data.py - generate og-data.json for the share-link Worker.

The Worker on druk.se/e/<id> needs a small, fast lookup of per-event Open Graph
fields. events.js is ~1.3 MB and not worth parsing on the edge, so we pre-build a
compact JSON file the Worker fetches and edge-caches.

Output: og-data.json at repo root.
Format (array per id keeps the file small):
    { "<event-id>": ["name", "description", "backImage",
                     "date", "dateEnd", "time", "location", "region", "organizer"] }
- backImage is the relative path (e.g. "ads/foo.jpg") or "" if none.
  The Worker turns it into an absolute URL and falls back to the site cover.
- Fields 3-8 (since 2026-07-05) feed the schema.org Event JSON-LD the Worker
  injects into /e/<id> pages. Old Worker versions ignore the extra fields.

Reads BOTH events.js (upcoming) and events-archive.js (past) so old shared
links still get a rich preview. Run it whenever events change (or before a push
that touches events.js). Safe to re-run.

Usage: python3 tools/build-og-data.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_events(filename):
    """Parse a `const X = { ... };` events file into a Python dict."""
    path = os.path.join(ROOT, filename)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        s = f.read()
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        return []
    data = json.loads(s[start:end + 1])
    return data.get("events", [])


def short_desc(ev):
    """Best short description for the preview, max ~200 chars."""
    d = (ev.get("description") or "").strip()
    if not d:
        full = (ev.get("descriptionFull") or "").replace("\n", " ").strip()
        d = full
    if len(d) > 200:
        d = d[:197].rstrip() + "..."
    return d


def main():
    upcoming = load_events("events.js")
    archive = load_events("events-archive.js")

    out = {}
    # archive first so upcoming (fresher) wins on any id clash
    for ev in archive + upcoming:
        eid = ev.get("id")
        if not eid:
            continue
        name = (ev.get("name") or "").strip()
        if not name:
            continue
        region = ev.get("region") or ""
        if isinstance(region, list):
            region = ", ".join(region)
        out[eid] = [
            name,
            short_desc(ev),
            # backImage preferred; poster cards (Type 2) often only have
            # frontImage - use it so previews/JSON-LD get a real image
            (ev.get("backImage") or ev.get("frontImage") or "").strip(),
            (ev.get("date") or "").strip(),
            (ev.get("dateEnd") or "").strip(),
            (ev.get("time") or "").strip(),
            (ev.get("location") or "").strip(),
            region.strip(),
            (ev.get("organizer") or "").strip(),
        ]

    dest = os.path.join(ROOT, "og-data.json")
    with open(dest, "w", encoding="utf-8") as f:
        # compact, but keep non-ascii readable (Swedish chars) and valid JSON
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

    size_kb = os.path.getsize(dest) / 1024
    print(f"Wrote {dest}")
    print(f"  events: {len(out)} (upcoming {len(upcoming)}, archive {len(archive)})")
    print(f"  size: {size_kb:.1f} KB")
    if size_kb > 800:
        print("  WARNING: og-data.json is large; consider trimming fields.", file=sys.stderr)


if __name__ == "__main__":
    main()
