#!/usr/bin/env python3
"""
MC Kalendern - Facebook Page Info Scraper
Uses Apify's Facebook Pages Scraper to get follower/following counts in batch.
Reads URLs from the Excel file, runs Apify, creates a new Excel with results.

Usage:
  python tools/fb-page-info.py                    # Run full batch
  python tools/fb-page-info.py --dry-run          # Show what would be checked
  python tools/fb-page-info.py --test 5           # Test with first 5 URLs only

Setup: Requires tools/.apify-token (same as fb-discover.py)
"""

import json
import sys
import time
import argparse
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TOKEN_FILE = SCRIPT_DIR / ".apify-token"
PAGES_FILE = SCRIPT_DIR / "fb_pages_for_apify.json"
GROUPS_FILE = SCRIPT_DIR / "fb_groups_manual.json"
OUTPUT_FILE = SCRIPT_DIR / "fb-page-info-results.json"

# Apify actor for Facebook Pages Scraper
ACTOR_ID = "apify~facebook-pages-scraper"


def load_token():
    if not TOKEN_FILE.exists():
        print(f"ERROR: Token file not found: {TOKEN_FILE}")
        sys.exit(1)
    return TOKEN_FILE.read_text().strip()


def api_call(url, token, data=None, timeout=300):
    full_url = f"{url}?token={token}"
    headers = {"Content-Type": "application/json"}
    if data:
        req = Request(full_url, data=json.dumps(data).encode(), headers=headers, method="POST")
    else:
        req = Request(full_url, headers=headers)
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as e:
        body = e.read().decode() if e.fp else ""
        print(f"API Error {e.code}: {body[:500]}")
        return None
    except URLError as e:
        print(f"Connection error: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Get Facebook page follower counts via Apify")
    parser.add_argument("--dry-run", action="store_true", help="Show URLs without running")
    parser.add_argument("--test", type=int, help="Test with first N URLs only")
    args = parser.parse_args()

    # Load URLs
    if not PAGES_FILE.exists():
        print(f"ERROR: {PAGES_FILE} not found. Run the Excel analysis first.")
        sys.exit(1)

    with open(PAGES_FILE) as f:
        pages = json.load(f)

    if args.test:
        pages = pages[:args.test]

    urls = [url for name, url in pages]

    if args.dry_run:
        print(f"Would check {len(urls)} Facebook pages:")
        for name, url in pages[:10]:
            print(f"  {name:45s} | {url}")
        if len(pages) > 10:
            print(f"  ... and {len(pages) - 10} more")
        return

    token = load_token()

    # Deduplicate URLs
    unique_urls = list(dict.fromkeys(urls))
    print(f"Checking {len(unique_urls)} unique URLs (removed {len(urls) - len(unique_urls)} duplicates)")

    # Process in batches of 20 to avoid Apify timeout
    BATCH_SIZE = 20
    all_results = []
    total_batches = (len(unique_urls) + BATCH_SIZE - 1) // BATCH_SIZE

    api_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/run-sync-get-dataset-items"
    start = time.time()

    for batch_num in range(total_batches):
        batch_start = batch_num * BATCH_SIZE
        batch_end = min(batch_start + BATCH_SIZE, len(unique_urls))
        batch_urls = unique_urls[batch_start:batch_end]

        print(f"  Batch {batch_num + 1}/{total_batches} ({len(batch_urls)} URLs)...", end=" ", flush=True)

        data = {"startUrls": [{"url": u} for u in batch_urls]}
        result = api_call(api_url, token, data=data, timeout=600)

        if result is None:
            print(f"FAILED (batch {batch_num + 1})")
            continue

        all_results.extend(result)
        print(f"got {len(result)} results")

        # Small delay between batches
        if batch_num < total_batches - 1:
            time.sleep(2)

    elapsed = time.time() - start
    print(f"\nTotal: {len(all_results)} results in {elapsed:.0f}s")

    if not all_results:
        print("No results received from Apify")
        sys.exit(1)

    result = all_results

    # Parse results
    parsed = {}
    for item in result:
        page_url = item.get("url", "") or item.get("facebookUrl", "")
        name = item.get("title", "") or item.get("name", "")
        followers = item.get("followers", item.get("followersCount"))
        likes = item.get("likes", item.get("likesCount"))
        following = item.get("following", item.get("followingCount"))

        # Try to match back to our input
        for orig_name, orig_url in pages:
            if orig_url in page_url or page_url in orig_url:
                parsed[orig_name] = {
                    "followers": followers,
                    "likes": likes,
                    "following": following,
                    "fb_name": name,
                    "url": orig_url,
                }
                break
        else:
            parsed[name or page_url] = {
                "followers": followers,
                "likes": likes,
                "following": following,
                "url": page_url,
            }

    # Save results
    output_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_sent": len(urls),
        "total_received": len(result),
        "total_parsed": len(parsed),
        "results": parsed,
    }
    OUTPUT_FILE.write_text(json.dumps(output_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {OUTPUT_FILE}")

    # Summary
    print(f"\n=== RESULTS ===")
    print(f"Sent: {len(urls)} URLs")
    print(f"Received: {len(result)} results")
    print(f"Matched: {len(parsed)} pages")

    # Show top 10 by followers
    sorted_pages = sorted(parsed.items(), key=lambda x: x[1].get("followers") or 0, reverse=True)
    print(f"\nTop 10 by followers:")
    for name, info in sorted_pages[:10]:
        f = info.get("followers") or "?"
        fg = info.get("following") or "?"
        print(f"  {name:45s} | {str(f):>8} followers | {str(fg):>5} following")


if __name__ == "__main__":
    main()
