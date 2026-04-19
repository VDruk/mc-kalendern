#!/usr/bin/env python3
"""
MC Kalendern - Places Generator
Reads events.js + LOCATION_COORDS from index.html, extracts high-confidence
places (street-level coords, 2+ events), auto-detects categories,
and outputs places.js.

Usage: python3 tools/generate-places.py
  --dry-run   Print summary without writing places.js
  --verbose   Show all places with details

Re-runnable: safe to run again when new events are added.
"""

import json
import re
import sys
import os
from collections import defaultdict
from datetime import date
import unicodedata

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EVENTS_FILE = os.path.join(PROJECT_DIR, "events.js")
INDEX_FILE = os.path.join(PROJECT_DIR, "index.html")
OUTPUT_FILE = os.path.join(PROJECT_DIR, "places.js")

# Minimum events at a location to qualify as a "place"
MIN_EVENTS = 2

# ── Category detection rules ──────────────────────────────────────────

CATEGORY_RULES = [
    # (category_id, swedish_label, match function)
    ("mc-handel", "MC-handlare", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "harley", "h-d", "probike", "yamaha", "indian", "mc-konsult", "mc konsult",
        "honda mc", "kawasaki", "triumph", "lelles mc", "sulas mc", "ktm",
        "bmw motorrad", "husqvarna mc", "ducati", "suzuki mc", "nilssons mc",
        "claessons motor", "italia bike", "bike trollhättan", "motorrad center",
        "johans mc", "mtl powersport", "desmocenter",
    ]) or any(kw in loc.lower() for kw in [
        "h-d store", "h-d linköping",
    ]) or any(kw in " ".join(orgs).lower() for kw in [
        "bike trollhättan", "harley-davidson trollhättan", "mtl powersport",
        "nilssons mc", "italia bike", "h-d store",
    ])),
    ("bensin", "Bensinstation", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "circle k", "okq8", "shell ", "st1", "preem", "biltema", "ingo",
        "tanka", "qstar", "ok ",
    ]) or re.match(r'^ok\s', loc.lower()) is not None),
    ("arena", "Arena/Bana", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "raceway", "ring ", "motorstadion", "trafikövningsplats", "motorbana",
        "gelleråsen", "tånga hed", "pepparrotsbanan", "rallycross",
        "travbana", "folkrace", "mantorp park",
    ])),
    ("camping", "Camping", lambda loc, orgs: "camping" in loc.lower()),
    ("mc-klubb", "MC-klubb", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "klubbkåken", "klubblokalen", "klubblokal", "klubbstuga",
        "mc-klubb", "mc klubb",
    ])),
    ("cafe", "Café/Restaurang", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "café", "cafe", "pizzeria", "pub ", "restaurang", "restaurant",
        "mcdonald", "vägkrogen", "krogen", "grill", "bageri", "konditori",
        "sigridslund", "vikingagrillen",
    ])),
    ("verkstad", "Verkstad", lambda loc, orgs: any(kw in loc.lower() for kw in [
        "verkstad", "service", "mek ",
    ])),
    # Default fallback handled separately
]


def parse_events():
    """Parse events.js and return list of event objects."""
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'const\s+EVENTS_DATA\s*=\s*(\{.*\})\s*;?\s*$', content, re.DOTALL)
    if not match:
        print("ERROR: Could not parse events.js", file=sys.stderr)
        sys.exit(1)
    data = json.loads(match.group(1))
    return data["events"]


def parse_location_coords():
    """Parse LOCATION_COORDS from index.html."""
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r'const\s+LOCATION_COORDS\s*=\s*\{(.*?)\};', content, re.DOTALL)
    if not match:
        print("ERROR: Could not find LOCATION_COORDS in index.html", file=sys.stderr)
        sys.exit(1)

    coords = {}
    block = match.group(1)
    for m in re.finditer(r"'([^']+)'\s*:\s*\{\s*lat:\s*([-\d.]+)\s*,\s*lon:\s*([-\d.]+)\s*\}", block):
        key = m.group(1).strip().lower()
        lat = float(m.group(2))
        lon = float(m.group(3))
        coords[key] = {"lat": lat, "lon": lon}
    return coords


def decimal_places(val):
    s = str(val)
    if '.' not in s:
        return 0
    return len(s.split('.')[1])


def is_street_level(lat, lon):
    """Check if coords have enough precision to be street-level."""
    return min(decimal_places(lat), decimal_places(lon)) >= 5


def find_coord_for_location(location, coords_dict):
    """Mimic longest-match logic from index.html."""
    if not location:
        return None, None
    loc_lower = location.lower()
    best_key = None
    best_len = 0
    for key in coords_dict:
        if key in loc_lower and len(key) > best_len:
            best_key = key
            best_len = len(key)
    if best_key:
        return best_key, coords_dict[best_key]
    return None, None


def slugify(text):
    """Create a URL-friendly slug from text."""
    text = text.lower().strip()
    # Normalize unicode
    text = unicodedata.normalize('NFKD', text)
    # Replace Swedish chars before stripping accents
    text = text.replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
    # Remove remaining accents
    text = ''.join(c for c in text if not unicodedata.combining(c))
    # Replace non-alphanumeric with hyphens
    text = re.sub(r'[^a-z0-9]+', '-', text)
    # Clean up
    text = text.strip('-')
    text = re.sub(r'-+', '-', text)
    return text


def normalize_location(loc):
    """Normalize location string for grouping similar locations."""
    loc = loc.strip()
    # Normalize unicode
    loc = unicodedata.normalize('NFC', loc)
    # Normalize whitespace
    loc = re.sub(r'\s+', ' ', loc)
    return loc


def detect_category(location, organizers):
    """Auto-detect place category from location name and organizers."""
    for cat_id, cat_label, match_fn in CATEGORY_RULES:
        if match_fn(location, organizers):
            return cat_id
    return "motesplats"  # Default fallback


def extract_place_name(location):
    """Extract a short display name from a full location string.

    E.g. "Circle K, Rapsgatan 1H, Uppsala" -> "Circle K"
         "Klubbkåken, Stångby 1, Uppsala" -> "Klubbkåken"
         "Industrivägen 4, Odensbacken" -> "Industrivägen 4, Odensbacken"
    """
    parts = [p.strip() for p in location.split(',')]

    # If first part looks like a venue name (not just street+number), use it
    first = parts[0]

    # Check if first part is just a street address (starts with number or is "Xvägen N")
    if re.match(r'^\d', first) or re.match(r'^[A-ZÅÄÖ][a-zåäö]+vägen\s+\d', first):
        # Use first two parts for address-only locations
        if len(parts) >= 2:
            return f"{parts[0]}, {parts[1]}"
        return first

    return first


def generate_note(location, organizers, event_types):
    """Generate a short note for the place."""
    notes = []

    if len(organizers) == 1:
        org = organizers[0]
        if "H-DCS" in org or "DOA" in org or "DOB" in org or "DOC" in org:
            notes.append(f"{org} samlingspunkt")

    if not notes:
        return ""

    return notes[0]


def merge_duplicate_locations(location_groups):
    """Merge locations that share the same coord_key (same physical place, different text)."""
    merged = {}

    for loc, data in location_groups.items():
        coord_key = data.get("coord_key")
        if not coord_key:
            continue

        if coord_key not in merged:
            merged[coord_key] = data
            merged[coord_key]["alt_locations"] = [loc]
        else:
            existing = merged[coord_key]
            existing["alt_locations"].append(loc)
            existing["event_count"] += data["event_count"]
            # Merge organizers
            for org in data["organizers"]:
                if org not in existing["organizers"]:
                    existing["organizers"].append(org)
            # Merge event types
            for t in data["types"]:
                if t not in existing["types"]:
                    existing["types"].append(t)
            # Merge regions
            for r in data["regions"]:
                if r not in existing["regions"]:
                    existing["regions"].append(r)
            # Keep the longer/more descriptive location as primary
            if len(loc) > len(existing["location"]):
                existing["location"] = loc

    return merged


def main():
    dry_run = "--dry-run" in sys.argv
    verbose = "--verbose" in sys.argv

    events = parse_events()
    coords_dict = parse_location_coords()

    # Group events by normalized location
    location_groups = {}

    for e in events:
        if e.get("_canary") or e.get("_ad"):
            continue
        loc = normalize_location(e.get("location", ""))
        if not loc:
            continue

        if loc not in location_groups:
            coord_key, coord = find_coord_for_location(loc, coords_dict)
            location_groups[loc] = {
                "location": loc,
                "organizers": [],
                "types": [],
                "regions": [],
                "event_count": 0,
                "coord_key": coord_key,
                "coord": coord,
            }

        g = location_groups[loc]
        g["event_count"] += 1

        org = e.get("organizer", "")
        if org and org not in g["organizers"]:
            g["organizers"].append(org)

        etype = e.get("type", "")
        if etype and etype not in g["types"]:
            g["types"].append(etype)

        region = e.get("region", "")
        if isinstance(region, list):
            for r in region:
                if r and r not in g["regions"]:
                    g["regions"].append(r)
        elif region and region not in g["regions"]:
            g["regions"].append(region)

    # Filter: must have street-level coords
    street_level_groups = {}
    for loc, data in location_groups.items():
        if data["coord"] and is_street_level(data["coord"]["lat"], data["coord"]["lon"]):
            street_level_groups[loc] = data

    # Merge duplicates (same coord_key = same physical place)
    merged = merge_duplicate_locations(street_level_groups)

    # Filter: minimum events
    qualified = {k: v for k, v in merged.items() if v["event_count"] >= MIN_EVENTS}

    # Build places list
    places = []
    used_ids = set()

    for coord_key, data in sorted(qualified.items(), key=lambda x: x[1]["event_count"], reverse=True):
        loc = data["location"]
        name = extract_place_name(loc)
        category = detect_category(loc, data["organizers"])
        region = data["regions"][0] if data["regions"] else "Sverige"
        note = generate_note(loc, data["organizers"], data["types"])

        # Generate unique ID
        slug = slugify(name)
        if not slug:
            slug = slugify(loc)
        # Add city for uniqueness if needed
        if slug in used_ids:
            city = slugify(data["regions"][0]) if data["regions"] else ""
            slug = f"{slug}-{city}" if city else f"{slug}-2"
        used_ids.add(slug)

        place = {
            "id": slug,
            "name": name,
            "address": loc,
            "category": category,
            "region": region,
            "lat": data["coord"]["lat"],
            "lon": data["coord"]["lon"],
            "organizers": data["organizers"],
            "eventCount": data["event_count"],
        }
        if note:
            place["note"] = note

        places.append(place)

    # Print summary
    print(f"{'=' * 60}")
    print(f"MC KALENDERN - PLACES GENERATOR")
    print(f"{'=' * 60}")
    print(f"Total unique locations:      {len(location_groups)}")
    print(f"With street-level coords:    {len(street_level_groups)}")
    print(f"After merging duplicates:    {len(merged)}")
    print(f"With {MIN_EVENTS}+ events (qualified):  {len(qualified)}")
    print(f"Places generated:            {len(places)}")
    print()

    # Category breakdown
    cat_counts = defaultdict(int)
    for p in places:
        cat_counts[p["category"]] += 1
    print("By category:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {cat:15s} {count}")
    print()

    # Region breakdown
    region_counts = defaultdict(int)
    for p in places:
        region_counts[p["region"]] += 1
    print("By region:")
    for reg, count in sorted(region_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {reg:20s} {count}")
    print()

    if verbose:
        print("All places:")
        for p in places:
            print(f"  [{p['eventCount']:3d}] {p['name']:30s} | {p['category']:12s} | {p['region']}")
            print(f"        {p['address']}")
            print(f"        Orgs: {', '.join(p['organizers'][:3])}")
        print()

    if dry_run:
        print("DRY RUN - places.js not written.")
        return

    # Write places.js
    today = date.today().isoformat()
    places_data = {
        "lastUpdated": today,
        "places": places
    }

    js_content = f"const PLACES_DATA = {json.dumps(places_data, ensure_ascii=False, indent=2)};\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(js_content)

    print(f"Written {len(places)} places to places.js")
    print(f"Last updated: {today}")


if __name__ == "__main__":
    main()
