#!/usr/bin/env python3
"""
build-events-feed.py - generate events.json, the public machine-readable feed.

Purpose: AI assistants and other non-JS clients cannot read the JavaScript-rendered
homepage. This feed gives them all UPCOMING events as clean JSON. It is advertised
in llms.txt. Runs automatically via .github/workflows/build-og-data.yml.

Output: events.json at repo root.
Format:
{
  "generated": "YYYY-MM-DD",
  "source": "https://druk.se/",
  "count": N,
  "events": [ { id, name, date, dateEnd, time, endTime, type, region,
                location, organizer, description, descriptionFull, url, links } ]
}

Excludes internal cards: canaries (_canary), ads and places (_ad). Internal
underscore fields are never exported. Past events are excluded (feed is for
"what is coming", the archive stays on the site).

Usage: python3 tools/build-events-feed.py
"""

import json
import os
from datetime import date

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
    out = []
    for ev in load_events("events.js"):
        if ev.get("_canary") or ev.get("_ad"):
            continue
        end = ev.get("dateEnd") or ev.get("date") or ""
        if not end or end < today:
            continue  # already over
        item = {
            "id": ev.get("id"),
            "name": ev.get("name"),
            "date": ev.get("date"),
            "dateEnd": ev.get("dateEnd"),
            "time": ev.get("time"),
            "endTime": ev.get("endTime"),
            "type": ev.get("type"),
            "region": ev.get("region"),
            "location": ev.get("location"),
            "organizer": ev.get("organizer"),
            "description": ev.get("description"),
            "descriptionFull": ev.get("descriptionFull"),
            "url": SITE + "/e/" + ev.get("id", ""),
            "links": [l for l in ev.get("links", []) if l.get("url")],
        }
        out.append({k: v for k, v in item.items() if v})

    out.sort(key=lambda e: (e.get("date") or "", e.get("id") or ""))

    dest = os.path.join(ROOT, "events.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(
            {"generated": today, "source": SITE + "/", "count": len(out), "events": out},
            f, ensure_ascii=False, separators=(",", ":"),
        )
    print(f"Wrote {dest}: {len(out)} upcoming events, {os.path.getsize(dest)/1024:.0f} KB")


if __name__ == "__main__":
    main()
