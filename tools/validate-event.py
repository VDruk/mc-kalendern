#!/usr/bin/env python3
"""
validate-event.py — Pre-flight validator for MC Kalendern events.

Run this BEFORE presenting any new or modified event to Slava.
If any check fails, fix it first. Never present a failing event.

Usage:
  python3 tools/validate-event.py EVENT_ID              # validate one event
  python3 tools/validate-event.py EVENT_ID1 EVENT_ID2   # validate multiple
  python3 tools/validate-event.py --last N              # validate last N events in file
  python3 tools/validate-event.py --all                 # validate all events (full audit)
"""

import json
import re
import sys
import os

# --- Config ---
VALID_TYPES = {"Träff", "Körning", "Show", "Fest", "Racing", "Plats", "Anons"}
VALID_REGIONS = {
    "Blekinge", "Dalarna", "Gotland", "Gävleborg", "Halland", "Jämtland",
    "Jönköping", "Kalmar", "Kronoberg", "Norrbotten", "Skåne", "Stockholm",
    "Södermanland", "Uppsala", "Värmland", "Västerbotten", "Västernorrland",
    "Västmanland", "Västra Götaland", "Örebro", "Östergötland",
    "Danmark", "Finland", "Italien", "Litauen", "Norge", "Portugal", "Spanien", "Sverige", "Tjeckien"
}
REQUIRED_FIELDS = ["id", "name", "date", "dateEnd", "location", "type", "organizer",
                   "description", "descriptionFull", "link", "links", "region", "source"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
EVENTS_FILE = os.path.join(PROJECT_DIR, "events.js")
INDEX_FILE = os.path.join(PROJECT_DIR, "index.html")
ADS_DIR = os.path.join(PROJECT_DIR, "ads")
CLUBS_DIR = os.path.join(PROJECT_DIR, "clubs", "normalized")


def load_events():
    """Load events from events.js"""
    with open(EVENTS_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    # Extract JSON from the EVENTS_DATA assignment
    match = re.search(r'const\s+EVENTS_DATA\s*=\s*(\{.*\})\s*;?\s*$', text, re.DOTALL)
    if not match:
        print("ERROR: Could not parse events.js")
        sys.exit(1)
    return json.loads(match.group(1))["events"]


def load_location_coords():
    """Load LOCATION_COORDS from index.html"""
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        text = f.read()
    # Find the LOCATION_COORDS block
    match = re.search(r'const\s+LOCATION_COORDS\s*=\s*\{(.*?)\}\s*;', text, re.DOTALL)
    if not match:
        print("WARNING: Could not parse LOCATION_COORDS from index.html")
        return {}

    coords = {}
    block = match.group(1)
    # Parse entries like 'key': { lat: 59.123, lon: 17.456 }
    for m in re.finditer(r"'([^']+)'\s*:\s*\{\s*lat\s*:\s*([\d.-]+)\s*,\s*lon\s*:\s*([\d.-]+)\s*\}", block):
        key = m.group(1)
        lat = m.group(2)
        lon = m.group(3)
        coords[key] = {"lat": lat, "lon": lon, "lat_decimals": len(lat.split(".")[-1]) if "." in lat else 0,
                        "lon_decimals": len(lon.split(".")[-1]) if "." in lon else 0}
    return coords


def find_longest_match(location, coords):
    """Find the longest matching LOCATION_COORDS key for a location string"""
    loc_lower = location.lower()
    best_key = None
    best_len = 0
    for key in coords:
        if key in loc_lower and len(key) > best_len:
            best_key = key
            best_len = len(key)
    return best_key


def validate_event(event, all_events, coords, errors, warnings):
    """Validate a single event. Appends to errors and warnings lists."""
    eid = event.get("id", "UNKNOWN")
    is_ad = event.get("_ad", False)
    is_canary = event.get("_canary", False)

    if is_canary:
        return  # skip canary validation

    # --- 1. Required fields ---
    if not is_ad:
        for field in REQUIRED_FIELDS:
            if field not in event or event[field] is None or event[field] == "":
                errors.append(f"[{eid}] Missing required field: {field}")

    # --- 2. backImage exists ---
    back = event.get("backImage", "")
    if back:
        back_path = os.path.join(PROJECT_DIR, back)
        if not os.path.exists(back_path):
            errors.append(f"[{eid}] backImage file not found: {back}")
    elif not is_ad:
        warnings.append(f"[{eid}] No backImage set")

    # --- 3. backImage is not default-back.jpg ---
    if back == "ads/default-back.jpg":
        errors.append(f"[{eid}] Uses default-back.jpg (must use event-specific image)")

    # --- 4. frontImage != backImage ---
    front = event.get("frontImage", "")
    if front and back and front == back:
        errors.append(f"[{eid}] frontImage is same as backImage")

    # --- 5. Valid type ---
    etype = event.get("type", "")
    if etype and etype not in VALID_TYPES:
        errors.append(f"[{eid}] Invalid type: '{etype}' (must be one of {VALID_TYPES})")

    # --- 6. Valid region ---
    region = event.get("region", "")
    if region and region not in VALID_REGIONS:
        errors.append(f"[{eid}] Invalid region: '{region}'")

    # --- 7. Swedish chars check ---
    for field in ["type", "region", "name", "description", "descriptionFull", "location"]:
        val = event.get(field, "")
        if val and isinstance(val, str):
            # Check for common missing Swedish chars
            if re.search(r'\bTraff\b', val):
                errors.append(f"[{eid}] '{field}' has 'Traff' instead of 'Träff'")
            if re.search(r'\bKorning\b', val):
                errors.append(f"[{eid}] '{field}' has 'Korning' instead of 'Körning'")

    # --- 8. Description length ---
    desc = event.get("description", "")
    if desc and (len(desc) < 80 or len(desc) > 250):
        warnings.append(f"[{eid}] Description length {len(desc)} chars (target: 100-200)")

    # --- 9. Location length ---
    loc = event.get("location", "")
    if loc and len(loc) > 80:
        warnings.append(f"[{eid}] Location too long: {len(loc)} chars (max 80)")

    # --- 10. descriptionFull should not start with event name ---
    dfull = event.get("descriptionFull", "")
    name = event.get("name", "")
    if dfull and name and dfull.strip().startswith(name):
        warnings.append(f"[{eid}] descriptionFull starts with event name")

    # --- 11. Link labels must match URL type ---
    links = event.get("links", [])
    for link in links:
        label = link.get("label", "")
        url = link.get("url", "")
        if "facebook.com" in url:
            if "/events/" in url and label == "Facebook":
                errors.append(f"[{eid}] FB event URL has label 'Facebook' instead of 'FB Event'")
            if "/events/" in url and label == "FB Sida":
                errors.append(f"[{eid}] FB event URL has label 'FB Sida' instead of 'FB Event'")
            if "/photo" in url and label != "FB Inlägg":
                errors.append(f"[{eid}] FB photo URL should have label 'FB Inlägg', not '{label}'")
            if label == "Facebook":
                warnings.append(f"[{eid}] Generic 'Facebook' label used. Use 'FB Event', 'FB Inlägg', or 'FB Sida'")

    # --- 12. Karta link when address exists ---
    # Street address = pattern like "Vägen 12" or "Gatan 5A" (number after a word)
    has_street = bool(re.search(r'[a-öA-Ö]+\s+\d+', loc)) and not is_ad
    has_karta = any(l.get("type") == "map" or l.get("label") == "Karta" for l in links)
    if has_street and not has_karta:
        warnings.append(f"[{eid}] Has street address but no Karta link")

    # --- 13. LOCATION_COORDS check ---
    if loc and not is_ad:
        matched_key = find_longest_match(loc, coords)
        if not matched_key:
            errors.append(f"[{eid}] No LOCATION_COORDS match for location: '{loc}'")
        elif matched_key:
            c = coords[matched_key]
            # For events with street addresses: matched coords MUST have full precision
            # City-level coords (2 decimals) are only OK for events without specific addresses
            if has_street and c["lat_decimals"] < 5:
                errors.append(f"[{eid}] LOCATION_COORDS '{matched_key}' lat has only {c['lat_decimals']} decimals ({c['lat']}). Event has a street address so needs its own LOCATION_COORDS entry with full Google Maps precision (7+ decimals). NEVER round.")
            if has_street and c["lon_decimals"] < 5:
                errors.append(f"[{eid}] LOCATION_COORDS '{matched_key}' lon has only {c['lon_decimals']} decimals ({c['lon']}). Event has a street address so needs its own LOCATION_COORDS entry with full Google Maps precision (7+ decimals). NEVER round.")
            # For ALL new entries (even city-level), warn if precision is suspiciously low
            # but only error for street-address events
            if not has_street and c["lat_decimals"] < 2:
                warnings.append(f"[{eid}] LOCATION_COORDS '{matched_key}' has very low precision ({c['lat_decimals']} decimals)")

    # --- 14. organizerIcon file exists ---
    icon = event.get("organizerIcon", "")
    if icon:
        icon_path = os.path.join(PROJECT_DIR, icon)
        if not os.path.exists(icon_path):
            errors.append(f"[{eid}] organizerIcon file not found: {icon}")

    # --- 15. Duplicate ID check ---
    dupes = [e for e in all_events if e.get("id") == eid]
    if len(dupes) > 1:
        errors.append(f"[{eid}] Duplicate event ID ({len(dupes)} occurrences)")

    # --- 16. Date format ---
    date = event.get("date", "")
    if date and not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
        errors.append(f"[{eid}] Invalid date format: '{date}' (must be YYYY-MM-DD)")

    dateEnd = event.get("dateEnd", "")
    if dateEnd and not re.match(r'^\d{4}-\d{2}-\d{2}$', dateEnd):
        errors.append(f"[{eid}] Invalid dateEnd format: '{dateEnd}'")

    # --- 17. dateEnd >= date ---
    if date and dateEnd and dateEnd < date:
        errors.append(f"[{eid}] dateEnd ({dateEnd}) is before date ({date})")


def main():
    events = load_events()
    coords = load_location_coords()

    # Determine which events to validate
    target_ids = set()
    validate_all = False
    last_n = 0

    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    if sys.argv[1] == "--all":
        validate_all = True
    elif sys.argv[1] == "--last":
        last_n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    else:
        target_ids = set(sys.argv[1:])

    # Select events to validate
    if validate_all:
        targets = events
    elif last_n:
        targets = events[-last_n:]
    else:
        targets = [e for e in events if e.get("id") in target_ids]
        found_ids = {e.get("id") for e in targets}
        missing = target_ids - found_ids
        if missing:
            print(f"WARNING: Event IDs not found: {missing}")

    if not targets:
        print("No events to validate.")
        sys.exit(0)

    # Run validation
    all_errors = []
    all_warnings = []

    for event in targets:
        validate_event(event, events, coords, all_errors, all_warnings)

    # Report
    print(f"\n{'='*60}")
    print(f"  MC Kalendern Event Validator")
    print(f"  Checked: {len(targets)} event(s)")
    print(f"{'='*60}\n")

    if all_errors:
        print(f"ERRORS ({len(all_errors)}):")
        for e in all_errors:
            print(f"  ✗ {e}")
        print()

    if all_warnings:
        print(f"WARNINGS ({len(all_warnings)}):")
        for w in all_warnings:
            print(f"  ⚠ {w}")
        print()

    if not all_errors and not all_warnings:
        print("  ✓ All checks passed!\n")

    if all_errors:
        print(f"RESULT: FAIL ({len(all_errors)} errors, {len(all_warnings)} warnings)")
        print("Fix all errors before presenting the event to Slava.")
        sys.exit(1)
    elif all_warnings:
        print(f"RESULT: PASS with {len(all_warnings)} warnings")
        sys.exit(0)
    else:
        print("RESULT: PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
