#!/usr/bin/env python3
"""
classify-vehicle.py - internal mc vs moped data for MC Kalendern.

Why: site analytics (2026-06-15) showed real search demand for "mopedrally"
events (esp. Östergötland). If moped traffic keeps growing we may add an
"mc/moped" filter. This tool gives the current mc-vs-moped split so we can
decide, and it keeps reporting as we tag events with the internal `_vehicle`
field ("moped" | "mc" | "both").

How it works:
- Reads events.js (upcoming) and events-archive.js (past).
- If an event has an explicit `_vehicle` field, that wins.
- Otherwise it guesses from keywords in name/description/type.
- Prints totals + a per-region moped breakdown. Read-only, edits nothing.

Run: python3 tools/classify-vehicle.py
"""
import json, re, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOPED_KW = [
    "moped", "mopped", "mopperally", "mopedrally", "mopedcruising",
    "mopedträff", "mopedtraff", "veteranmoped", "moppe", "mopprally",
]
# strong MC-only hints (avoid classing these as moped just because "mc" appears)
MC_KW = ["motorcykel", "mc-träff", "mc träff", "knixkurs", "hoj"]

def load(path, varname):
    if not os.path.exists(path):
        return []
    s = open(path, encoding="utf-8").read()
    s = re.sub(r"/\*[\s\S]*?\*/", "", s, count=1)          # strip copyright header
    s = re.sub(r"const\s+" + varname + r"\s*=", "", s, count=1)
    s = s.strip().rstrip(";").strip()
    data = json.loads(s)
    return data["events"] if isinstance(data, dict) else data

def classify(ev):
    if ev.get("_vehicle"):
        return ev["_vehicle"]
    blob = " ".join(str(ev.get(k, "")) for k in
                    ("name", "description", "descriptionFull", "type")).lower()
    has_moped = any(k in blob for k in MOPED_KW)
    has_mc = any(k in blob for k in MC_KW)
    if has_moped and has_mc:
        return "both"
    if has_moped:
        return "moped"
    return "mc"  # default: this is an MC calendar

def run():
    up = load(os.path.join(ROOT, "events.js"), "EVENTS_DATA")
    arch = load(os.path.join(ROOT, "events-archive.js"), "EVENTS_ARCHIVE")
    allev = [e for e in (up + arch)
             if not e.get("_canary") and not e.get("_ad")]  # real events only

    counts = {"moped": 0, "mc": 0, "both": 0}
    tagged = 0
    moped_by_region = {}
    for e in allev:
        v = classify(e)
        counts[v] = counts.get(v, 0) + 1
        if e.get("_vehicle"):
            tagged += 1
        if v in ("moped", "both"):
            for r in (e.get("region") if isinstance(e.get("region"), list)
                      else [e.get("region")]):
                if r:
                    moped_by_region[r] = moped_by_region.get(r, 0) + 1

    total = sum(counts.values())
    print("=" * 52)
    print("  MC Kalendern - vehicle split (real events only)")
    print("=" * 52)
    print(f"  Total real events : {total}")
    print(f"  MC                : {counts['mc']}  ({counts['mc']*100//total}%)")
    print(f"  Moped             : {counts['moped']}  ({counts['moped']*100//total}%)")
    print(f"  Both moped & MC   : {counts['both']}")
    print(f"  Explicitly tagged : {tagged} (via _vehicle field)")
    print("-" * 52)
    print("  Moped/both events by region (search-demand check):")
    for r, n in sorted(moped_by_region.items(), key=lambda x: -x[1]):
        print(f"    {r:<22} {n}")
    print("=" * 52)
    print("Note: untagged events are guessed by keyword. Tag events with")
    print('"_vehicle": "moped" | "mc" | "both" to make the data exact.')

if __name__ == "__main__":
    run()
