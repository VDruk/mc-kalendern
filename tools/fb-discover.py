#!/usr/bin/env python3
"""
MC Kalendern - Facebook Event Discovery Tool
Uses Apify to search Facebook for MC events in Sweden.
Deduplicates against existing events.js.

Usage:
  python fb-discover.py                  # Run all keyword searches
  python fb-discover.py --keyword "MC"   # Run single keyword
  python fb-discover.py --dry-run        # Show what would be searched (no API call)
  python fb-discover.py --budget         # Show remaining Apify credits

Setup:
  1. Create file: tools/.apify-token
  2. Paste your Apify API token in it (one line, no spaces)
  3. Get token from: https://console.apify.com/settings/integrations
"""

import json
import os
import sys
import time
import argparse
import re
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
# Based on analysis of 777 existing events in MC Kalendern
SEARCH_KEYWORDS = [
    # Core MC terms (Swedish)
    "MC träff",
    "MC körning",
    "MC mässa",
    "motorcykel",
    "bikerfest",
    # Seasonal / specific
    "avrostning MC",
    "säsongsstart MC",
    "MC tur Sverige",
    # Event types
    "custom bike show",
    "MC racing Sverige",
    "hoj träff",
    # Club-related (smaller clubs we might miss)
    "MC-klubb träff",
    "biker meet Sweden",
]

# Max pages per keyword (1 page ~ 5-10 results, costs ~$0.02)
MAX_PAGES_PER_KEYWORD = 2


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
    """Load events from events.js and extract Facebook event IDs and URLs."""
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
                # Extract event ID from URL
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


def is_likely_swedish(title):
    """Check if event title looks Swedish/Nordic."""
    swedish_indicators = [
        "träff", "körning", "tur", "mässa", "fest", "klubb",
        "hoj", "öppet", "dag", "kväll", "årsmöte", "avrostning",
        "lördag", "söndag", "fredag", "sweden", "sverige",
        "stockholm", "göteborg", "malmö", "uppsala", "norr",
        "söder", "väster", "öster", "mc-", "moped",
        "ä", "ö", "å",  # Swedish chars as indicator
    ]
    title_lower = title.lower()
    return any(indicator in title_lower for indicator in swedish_indicators)


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
    parser = argparse.ArgumentParser(description="MC Kalendern - Facebook Event Discovery")
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
            usage = resp.get("proxy", {})
            print(f"Account: {resp.get('username', '?')}")
            print(f"Plan: {plan.get('id', '?')}")
            # Note: exact balance might need different endpoint
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

    for item in all_results:
        eid = item.get("event_id", "")
        title = item.get("title", "").strip()
        url = item.get("url", "")

        # Skip if we already have this event
        if eid in existing_fb_ids:
            skipped_existing += 1
            continue

        # Check fuzzy name match
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

        new_events.append(item)

    # Report
    print(f"\nResults:")
    print(f"  Skipped (already in events.js): {skipped_existing}")
    print(f"  Skipped (not Swedish): {skipped_non_swedish}")
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
