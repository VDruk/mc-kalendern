#!/usr/bin/env python3
"""
MC Kalendern - Facebook Event Discovery Tool (v2)
Uses Apify to search Facebook for MC events in Sweden.
Deduplicates against existing events.js.

Usage:
  python fb-discover.py                  # Run all keyword searches
  python fb-discover.py --keyword "MC"   # Run single keyword
  python fb-discover.py --dry-run        # Show what would be searched (no API call)
  python fb-discover.py --budget         # Show remaining Apify credits
  python fb-discover.py --all-results    # Show all results including non-Swedish

Setup:
  1. Create file: tools/.apify-token
  2. Paste your Apify API token in it (one line, no spaces)
  3. Get token from: https://console.apify.com/settings/integrations

v2 changes (2026-03-17):
  - Removed 5 zero-result keywords, removed "bikerfest" (only non-Swedish results)
  - Added negative language filter (German, Italian, English patterns)
  - Added past event detection (skips events before today)
  - Added cross-result dedup (same event from different FB pages)
  - Better Swedish detection with location-based checks
"""

import json
import os
import sys
import time
import argparse
import re
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ============================================================
# Configuration
# ============================================================

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
EVENTS_FILE = PROJECT_DIR / "events.js"
TOKEN_FILE = SCRIPT_DIR / ".apify-token"

# Apify Actor ID for "Facebook Events Scraper (No Login Required)" by Iron Crawler
ACTOR_ID = "iron-crawler~facebook-search-events"

# Search keywords optimized for Swedish MC events
# Based on analysis of 780 existing events + first run results (2026-03-17)
# Removed: "MC körning", "MC tur Sverige", "MC racing Sverige", "hoj träff",
#          "MC-klubb träff" (all returned 0), "bikerfest" (only non-Swedish results)
SEARCH_KEYWORDS = [
    # Core Swedish MC terms (best performers: 9-16 results each)
    "MC träff",
    "MC mässa",
    "motorcykel",
    "avrostning MC",
    "säsongsstart MC",
    # Targeted Swedish terms
    "MC evenemang",
    "motorcykelträff",
    "MC kväll Sverige",
    "Harley Night Sverige",
    # English terms with Sweden filter
    "custom bike show Sweden",
    "biker meet Sweden",
    "motorcycle event Sweden",
]

# Max pages per keyword (1 page ~ 5-10 results, costs ~$0.02)
MAX_PAGES_PER_KEYWORD = 2


# ============================================================
# Language detection
# ============================================================

# Strong Swedish indicators (if any present, likely Swedish)
SWEDISH_POSITIVE = [
    "träff", "körning", "tur", "mässa", "fest", "klubb",
    "hoj", "öppet", "dag", "kväll", "årsmöte", "avrostning",
    "lördag", "söndag", "fredag", "sverige", "säsong",
    "stockholm", "göteborg", "malmö", "uppsala", "jönköping",
    "linköping", "västerås", "örebro", "helsingborg", "norrköping",
    "umeå", "lund", "sundsvall", "gävle", "borås", "eskilstuna",
    "halmstad", "karlstad", "växjö", "trollhättan", "norr",
    "söder", "väster", "öster", "mc-", "moped",
    "å", "ä", "ö",  # Swedish chars
]

# Non-Swedish indicators (German, Italian, English-only events)
NON_SWEDISH_NEGATIVE = [
    # German
    "bikerfest mit", "motorradweihe", "zugunsten", "schmetterling",
    "gemeinsame", "ausfahrt", "beim", "gurken", "spreewald",
    "leopoldsdorfer", "zu gunsten",
    # Italian
    "lignano", "sabbiadoro", "al bikerfest",
    # English-only (no Swedish connection)
    "dirty rotten", "block party", "annual",
    "50cc fever", "area4x4",
    # Generic non-Swedish location names
    "york", "texas", "florida", "california",
]

# Swedish city/region names for location-based detection
SWEDISH_LOCATIONS = [
    "stockholm", "göteborg", "malmö", "uppsala", "linköping",
    "västerås", "örebro", "helsingborg", "norrköping", "jönköping",
    "umeå", "lund", "sundsvall", "gävle", "borås", "eskilstuna",
    "halmstad", "karlstad", "växjö", "trollhättan", "luleå",
    "kalmar", "karlskrona", "falun", "skellefteå", "varberg",
    "kristianstad", "skövde", "uddevalla", "visby", "östersund",
    "motala", "nyköping", "strömstad", "svedala", "oxie",
    "elmia", "sweden", "sverige",
]


def is_likely_swedish(title):
    """Check if event title looks Swedish/Nordic. Improved v2 with negative filters."""
    title_lower = title.lower()

    # First check negative patterns (strong signal of non-Swedish)
    for neg in NON_SWEDISH_NEGATIVE:
        if neg in title_lower:
            return False

    # Then check positive patterns
    for pos in SWEDISH_POSITIVE:
        if pos in title_lower:
            return True

    # Check if title contains a known Swedish location
    for loc in SWEDISH_LOCATIONS:
        if loc in title_lower:
            return True

    return False


# ============================================================
# Past event detection
# ============================================================

# Known past events (event name patterns that are definitely past)
# Updated each time we identify past events in results
KNOWN_PAST_PATTERNS = [
    r"elmia.*januari",
    r"elmia.*jan\b",
    r"23.*25.*januari.*2026",  # MC-Mässan på Elmia 23 - 25 januari 2026
]


def is_likely_past_event(title):
    """Check if event title suggests it already happened."""
    title_lower = title.lower()
    for pattern in KNOWN_PAST_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False


# ============================================================
# Cross-result deduplication
# ============================================================

def stem_swedish_mc_word(word):
    """Simple Swedish stemming for MC event words.
    Handles: mässan->mässa, träffen->träff, körningen->körning, etc.
    """
    stems = {
        "mässan": "mässa", "mässor": "mässa", "mässorna": "mässa",
        "träffen": "träff", "träffar": "träff", "träffarna": "träff",
        "körningen": "körning", "körningar": "körning",
        "avrostningen": "avrostning",
        "festen": "fest", "fester": "fest",
        "showen": "show",
    }
    return stems.get(word, word)


def normalize_event_name(title):
    """Normalize event name for cross-result dedup.
    'MC Mässan Elmia', 'Mc mässan Elmia', 'Mc Mässa Elmia' -> similar tokens.
    """
    t = title.lower().strip()
    # Remove common noise
    t = re.sub(r'[!?,.\-:;|]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Extract meaningful words, apply stemming
    stop = {"mc", "i", "på", "med", "och", "för", "av", "den", "det",
            "2026", "2025", "the", "a", "an", "app", "no", "nr"}
    words = sorted(set(stem_swedish_mc_word(w) for w in t.split() if w not in stop and len(w) > 1))
    return " ".join(words)


def is_cross_duplicate(title, seen_normalized):
    """Check if this event is a duplicate of another result in the same batch."""
    norm = normalize_event_name(title)

    # Check word overlap with already-seen events
    norm_words = set(norm.split())
    for seen_norm in seen_normalized:
        seen_words = set(seen_norm.split())
        if not norm_words or not seen_words:
            continue
        overlap = norm_words & seen_words
        # If 60%+ overlap, it is probably the same event
        similarity = len(overlap) / min(len(norm_words), len(seen_words))
        if similarity >= 0.6:
            return True

    return False


# ============================================================
# Helpers
# ============================================================

def load_token():
    """Load Apify API token from .apify-token file."""
    if not TOKEN_FILE.exists():
        print(f"ERROR: Token file not found: {TOKEN_FILE}")
        print(f"Create it with: echo 'YOUR_TOKEN_HERE' > {TOKEN_FILE}")
        print(f"Get your token from: https://console.apify.com/settings/integrations")
        sys.exit(1)

    token = TOKEN_FILE.read_text().strip()
    if not token:
        print("ERROR: Token file is empty")
        sys.exit(1)

    return token


def api_call(url, token, method="GET", data=None):
    """Make an API call to Apify."""
    full_url = f"{url}?token={token}"
    headers = {"Content-Type": "application/json"}

    if data:
        req = Request(full_url, data=json.dumps(data).encode(), headers=headers, method="POST")
    else:
        req = Request(full_url, headers=headers, method=method)

    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"API Error {e.code}: {body[:200]}")
        return None
    except URLError as e:
        print(f"Connection error: {e}")
        return None


def load_existing_events():
    """Load events from events.js and extract Facebook event IDs and names."""
    if not EVENTS_FILE.exists():
        print(f"WARNING: {EVENTS_FILE} not found")
        return set(), set()

    content = EVENTS_FILE.read_text(encoding="utf-8")

    # Extract JSON from const declaration
    json_start = content.index("{")
    json_str = content[json_start:].rstrip().rstrip(";")
    data = json.loads(json_str)

    existing_fb_ids = set()
    existing_names_lower = set()

    for event in data.get("events", []):
        # Collect Facebook event IDs from links
        for link in event.get("links", []):
            url = link.get("url", "")
            if "facebook.com/events/" in url:
                match = re.search(r"facebook\.com/events/(\d+)", url)
                if match:
                    existing_fb_ids.add(match.group(1))

        # Also check the main link field
        link = event.get("link", "")
        if "facebook.com/events/" in link:
            match = re.search(r"facebook\.com/events/(\d+)", link)
            if match:
                existing_fb_ids.add(match.group(1))

        # Collect normalized event names for fuzzy matching
        name = event.get("name", "").lower().strip()
        if name:
            existing_names_lower.add(name)

    return existing_fb_ids, existing_names_lower


def run_search(token, keyword, max_pages=MAX_PAGES_PER_KEYWORD):
    """Run a single Apify search and return results."""
    print(f"  Searching: \"{keyword}\" (max {max_pages} pages)...", end=" ", flush=True)

    url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    data = {
        "query": keyword,
        "maxPages": max_pages
    }

    result = api_call(url, token, data=data)

    if result is None:
        print("FAILED")
        return []

    print(f"got {len(result)} results")
    return result


def name_similarity(name1, name2):
    """Simple word overlap check between two event names."""
    words1 = set(name1.lower().split())
    words2 = set(name2.lower().split())
    # Remove very common words
    stop = {"mc", "i", "på", "med", "och", "för", "av", "den", "det", "-", "&"}
    words1 -= stop
    words2 -= stop
    if not words1 or not words2:
        return 0
    overlap = words1 & words2
    return len(overlap) / min(len(words1), len(words2))


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="MC Kalendern - Facebook Event Discovery v2")
    parser.add_argument("--keyword", type=str, help="Run single keyword search")
    parser.add_argument("--keywords", type=str, help="Comma-separated keywords")
    parser.add_argument("--pages", type=int, default=MAX_PAGES_PER_KEYWORD, help="Max pages per keyword")
    parser.add_argument("--dry-run", action="store_true", help="Show keywords without running")
    parser.add_argument("--budget", action="store_true", help="Show Apify account balance")
    parser.add_argument("--all-results", action="store_true", help="Show all results, not just Swedish")
    args = parser.parse_args()

    # Determine keywords
    if args.keyword:
        keywords = [args.keyword]
    elif args.keywords:
        keywords = [k.strip() for k in args.keywords.split(",")]
    else:
        keywords = SEARCH_KEYWORDS

    # Dry run
    if args.dry_run:
        print(f"Would search {len(keywords)} keywords (max {args.pages} pages each):")
        for kw in keywords:
            print(f"  - \"{kw}\"")
        est_cost = len(keywords) * args.pages * 0.02
        print(f"\nEstimated cost: ~${est_cost:.2f}")
        return

    # Load token
    token = load_token()

    # Budget check
    if args.budget:
        resp = api_call("https://api.apify.com/v2/users/me", token)
        if resp:
            plan = resp.get("plan", {})
            print(f"Account: {resp.get('username', '?')}")
            print(f"Plan: {plan.get('id', '?')}")
            print("Check https://console.apify.com/billing for exact balance")
        return

    # Load existing events for dedup
    print("Loading existing events...")
    existing_fb_ids, existing_names = load_existing_events()
    print(f"  Found {len(existing_fb_ids)} Facebook event IDs in events.js")
    print(f"  Found {len(existing_names)} event names for fuzzy matching")
    print()

    # Run searches
    all_results = []
    seen_event_ids = set()

    print(f"Running {len(keywords)} keyword searches...")
    print("=" * 60)

    for kw in keywords:
        results = run_search(token, kw, args.pages)
        for item in results:
            eid = item.get("event_id", "")
            if eid and eid not in seen_event_ids:
                seen_event_ids.add(eid)
                all_results.append(item)
        # Small delay between searches to be nice
        time.sleep(1)

    print("=" * 60)
    print(f"\nTotal unique results: {len(all_results)}")

    if not all_results:
        print("No events found. Try different keywords.")
        return

    # Dedup and filter
    new_events = []
    skipped_existing = 0
    skipped_non_swedish = 0
    skipped_past = 0
    skipped_cross_dup = 0
    seen_normalized = []

    for item in all_results:
        eid = item.get("event_id", "")
        title = item.get("title", "").strip()

        # Skip if we already have this event (by FB ID)
        if eid in existing_fb_ids:
            skipped_existing += 1
            continue

        # Check fuzzy name match against events.js
        is_name_match = False
        for existing_name in existing_names:
            if name_similarity(title, existing_name) > 0.6:
                is_name_match = True
                break

        if is_name_match:
            skipped_existing += 1
            continue

        # Filter non-Swedish events (unless --all-results)
        if not args.all_results and not is_likely_swedish(title):
            skipped_non_swedish += 1
            continue

        # Filter past events
        if is_likely_past_event(title):
            skipped_past += 1
            continue

        # Cross-result dedup (same event from different FB pages)
        if is_cross_duplicate(title, seen_normalized):
            skipped_cross_dup += 1
            continue

        seen_normalized.append(normalize_event_name(title))
        new_events.append(item)

    # Report
    print(f"\nResults:")
    print(f"  Skipped (already in events.js): {skipped_existing}")
    print(f"  Skipped (not Swedish): {skipped_non_swedish}")
    print(f"  Skipped (past events): {skipped_past}")
    print(f"  Skipped (cross-duplicates): {skipped_cross_dup}")
    print(f"  NEW events to review: {len(new_events)}")
    print()

    if not new_events:
        print("No new Swedish MC events found this time!")
        return

    # Display new events
    print("=" * 60)
    print("NEW EVENTS FOUND:")
    print("=" * 60)
    for i, item in enumerate(new_events, 1):
        title = item.get("title", "?")
        url = item.get("url", "?")
        print(f"\n{i}. {title}")
        print(f"   {url}")

    # Save results to JSON
    output_file = SCRIPT_DIR / "discovery-results.json"
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "keywords_used": keywords,
        "total_found": len(all_results),
        "new_events": len(new_events),
        "skipped_existing": skipped_existing,
        "skipped_non_swedish": skipped_non_swedish,
        "skipped_past": skipped_past,
        "skipped_cross_dup": skipped_cross_dup,
        "events": [
            {
                "event_id": item.get("event_id", ""),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
            }
            for item in new_events
        ]
    }
    output_file.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {output_file}")
    print("\nNext steps:")
    print("  1. Review the events above")
    print("  2. Open interesting URLs in your browser")
    print("  3. Send the FB link + screenshot to Claude to create a card")


if __name__ == "__main__":
    main()
