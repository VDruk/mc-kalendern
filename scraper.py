#!/usr/bin/env python3
"""
MC Kalendern Event Scraper
Crawls Swedish MC event websites and merges into events.js

Run locally: python3 scraper.py
Run via GitHub Actions: see .github/workflows/scrape.yml

Requirements: pip install requests beautifulsoup4
"""

import json
import re
import sys
from datetime import datetime, date
from html import unescape

import requests
from bs4 import BeautifulSoup

# ---- Config ----
OUTPUT_FILE = "events.js"
USER_AGENT = "MCKalendern/1.0 (druk.se event aggregator)"
HEADERS = {"User-Agent": USER_AGENT}
TODAY = date.today().isoformat()
YEAR = str(date.today().year)

# ---- Region mappings ----

HDCS_DISTRICT_REGIONS = {
    "Distrikt A": "Stockholm",
    "Distrikt B": "Skåne",
    "Distrikt C": "Halland",
    "Distrikt D": "Västra Götaland",
    "Distrikt E": "Östergötland",
    "Distrikt F": "Gotland",
    "Distrikt G": "Dalarna",
    "Distrikt H": "Värmland",
    "Distrikt I": "Västernorrland",
    "Distrikt J": "Norrbotten",
    "Distrikt K": "Blekinge",
}

BMW_DISTRICT_REGIONS = {
    "D1": "Norrbotten", "D2": "Västerbotten", "D3": "Västernorrland",
    "D4": "Dalarna", "D5": "Västmanland", "D6": "Värmland",
    "D7": "Stockholm", "D8": "Uppland", "D9": "Östergötland",
    "D10": "Västra Götaland", "D11": "Småland", "D12": "Halland",
    "D14": "Gotland", "D15": "Skåne",
}

CITY_REGIONS = {
    "stockholm": "Stockholm", "solna": "Stockholm", "nacka": "Stockholm",
    "täby": "Stockholm", "norrtälje": "Stockholm", "skärholmen": "Stockholm",
    "bromma": "Stockholm", "huddinge": "Stockholm", "ekerö": "Stockholm",
    "göteborg": "Västra Götaland", "vårgårda": "Västra Götaland",
    "trollhättan": "Västra Götaland", "skövde": "Västra Götaland",
    "borås": "Västra Götaland", "götene": "Västra Götaland",
    "mölndal": "Västra Götaland",
    "malmö": "Skåne", "lund": "Skåne", "kågeröd": "Skåne",
    "helsingborg": "Skåne", "kristianstad": "Skåne",
    "halmstad": "Halland", "varberg": "Halland", "falkenberg": "Halland",
    "jönköping": "Småland", "anderstorp": "Småland", "växjö": "Småland",
    "västerås": "Västmanland", "eskilstuna": "Västmanland",
    "linköping": "Östergötland", "norrköping": "Östergötland",
    "mantorp": "Östergötland", "motala": "Östergötland",
    "örebro": "Närke", "karlskoga": "Närke",
    "uppsala": "Uppland",
    "umeå": "Västerbotten", "lycksele": "Västerbotten",
    "luleå": "Norrbotten", "gällivare": "Norrbotten", "kiruna": "Norrbotten",
    "sundsvall": "Västernorrland", "örnsköldsvik": "Västernorrland",
    "kramfors": "Västernorrland", "härnösand": "Västernorrland",
    "östersund": "Jämtland",
    "falun": "Dalarna", "mora": "Dalarna", "hedemora": "Dalarna",
    "borlänge": "Dalarna",
    "karlstad": "Värmland", "arvika": "Värmland",
    "ockelbo": "Gävleborg", "gävle": "Gävleborg", "sandviken": "Gävleborg",
    "gotland": "Gotland", "visby": "Gotland",
    "karlskrona": "Blekinge", "ronneby": "Blekinge",
    "strängnäs": "Södermanland",
}


# ---- Helpers ----

def make_id(name, datestr, prefix=""):
    """Create a kebab-case id from name and date"""
    slug = name.lower()
    # Replace Swedish characters
    for old, new in [("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e")]:
        slug = slug.replace(old, new)
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')[:50]
    year = datestr[:4] if datestr else YEAR
    if prefix:
        return f"{prefix}-{slug}-{year}"
    return f"{slug}-{year}"


def clean_html(text):
    """Strip HTML tags, decode entities, clean whitespace"""
    if not text:
        return ""
    text = re.sub(r'<[^>]+>', '', str(text))
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:250]


def safe_get(url, timeout=15):
    """HTTP GET with error handling"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN: Could not fetch {url}: {e}")
        return None


def guess_region(city):
    """Guess Swedish region from city name"""
    if not city:
        return "Sverige"
    city_lower = city.lower()
    for key, region in CITY_REGIONS.items():
        if key in city_lower:
            return region
    return "Sverige"


def detect_event_type(title, tag=""):
    """Detect event type from title and optional tag"""
    t = (title + " " + tag).lower()
    if any(w in t for w in ["mässa", "marknad", "expo"]):
        return "Mässa"
    if any(w in t for w in ["racing", "roadracing", "tävling", "race"]):
        return "Racing"
    if any(w in t for w in ["tur", "körning", "ride", "mc-tur", "utflykt", "on bike", "dagstur"]):
        return "Tur"
    if any(w in t for w in ["show", "bike show", "bikeshow"]):
        return "Show"
    if any(w in t for w in ["fest", "party", "gala", "rock"]):
        return "Fest"
    if any(w in t for w in ["trackday", "bandag", "banträning"]):
        return "Trackday"
    if any(w in t for w in ["kurs", "utbildning", "övning", "gps", "online"]):
        return "Körning"
    if any(w in t for w in ["träff", "fika", "samling", "pub", "afterwork", "soppkväll"]):
        return "Träff"
    return "Träff"


# ---- Scrapers ----

def scrape_hdcs():
    """
    Scrape H-DCS via WordPress REST API (The Events Calendar plugin).
    Endpoint: /wp-json/tribe/events/v1/events
    Returns paginated JSON with full event data.
    """
    print("Scraping H-DCS (hdcs.se)...")
    events = []
    page = 1

    while True:
        url = (
            f"https://hdcs.se/wp-json/tribe/events/v1/events"
            f"?per_page=50&start_date={TODAY}&end_date={YEAR}-12-31&page={page}"
        )
        r = safe_get(url)
        if not r:
            break

        data = r.json()
        if page == 1:
            print(f"  Found {data.get('total', 0)} events total")

        for e in data.get("events", []):
            title = clean_html(e.get("title", ""))
            start = (e.get("start_date") or "")[:10]
            end = (e.get("end_date") or "")[:10]
            venue = e.get("venue") or {}
            city = venue.get("city", "")
            venue_name = venue.get("venue", "")
            desc = clean_html(e.get("description", ""))
            link = e.get("url", "")
            cats = [c.get("name", "") for c in (e.get("categories") or [])]

            # Region from district category, fallback to city
            region = "Sverige"
            for cat in cats:
                if cat in HDCS_DISTRICT_REGIONS:
                    region = HDCS_DISTRICT_REGIONS[cat]
                    break
            if region == "Sverige" and city:
                region = guess_region(city)

            location = ", ".join(filter(None, [venue_name, city])) or "Se länk"

            events.append({
                "id": make_id(title, start),
                "name": title,
                "date": start,
                "dateEnd": end if end != start else start,
                "location": location,
                "type": detect_event_type(title),
                "organizer": "H-DCS",
                "description": desc or title,
                "link": link,
                "region": region,
                "source": "hdcs.se"
            })

        if not data.get("next_rest_url"):
            break
        page += 1

    print(f"  Extracted {len(events)} events from H-DCS")
    return events


def scrape_bmw_klubben():
    """
    Scrape BMW MC-klubben via their WordPress REST API.
    They use a custom post type 'aktivitet' with WP REST API.
    """
    print("Scraping BMW MC-klubben (bmwklubben.se)...")
    events = []
    page = 1
    per_page = 50

    while True:
        url = (
            f"https://www.bmwklubben.se/wp-json/wp/v2/aktivitet"
            f"?per_page={per_page}&page={page}&orderby=date&order=asc"
            f"&status=publish"
        )
        r = safe_get(url)
        if not r:
            # Fallback: try the page scraping approach
            print("  API not accessible, trying HTML scraping...")
            return scrape_bmw_klubben_html()

        try:
            posts = r.json()
        except Exception:
            break

        if not posts or not isinstance(posts, list):
            break

        for post in posts:
            title = clean_html(post.get("title", {}).get("rendered", ""))
            # BMW uses ACF or custom fields for dates
            acf = post.get("acf", {}) or {}
            meta = post.get("meta", {}) or {}

            date_time = acf.get("date_time") or meta.get("date_time") or ""
            date_time_end = acf.get("date_time_end") or meta.get("date_time_end") or ""

            start = date_time[:10] if date_time else ""
            end = date_time_end[:10] if date_time_end else start

            address = acf.get("address") or meta.get("address") or ""
            city = acf.get("city") or meta.get("city") or ""
            location = address or city or "Se länk"

            link = post.get("link", "https://www.bmwklubben.se/aktiviteter/")

            # District info from taxonomy
            district_ids = post.get("distrikt", []) or []

            events.append({
                "id": make_id(title, start, "bmw"),
                "name": title,
                "date": start,
                "dateEnd": end,
                "location": location[:150],
                "type": detect_event_type(title),
                "organizer": "BMW MC-klubben",
                "description": clean_html(post.get("excerpt", {}).get("rendered", "")),
                "link": link,
                "region": "Sverige",  # Will be refined if districts are available
                "source": "bmwklubben.se"
            })

        # Check if there are more pages
        total_pages = int(r.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1

    print(f"  Extracted {len(events)} events from BMW MC-klubben")
    return events


def scrape_bmw_klubben_html():
    """
    Fallback: Scrape BMW MC-klubben from the HTML page.
    Their page uses Alpine.js with lazy loading (VISA FLER button).
    We scrape what's in the initial page load.
    """
    print("  Trying HTML scraping for BMW...")
    url = "https://www.bmwklubben.se/aktiviteter/"
    r = safe_get(url)
    if not r:
        return []

    events = []
    soup = BeautifulSoup(r.text, "html.parser")

    # Extract Alpine.js data from inline scripts
    # Look for x-data containing posts
    for script in soup.find_all("script"):
        text = script.string or ""
        if "allFutureActivities" in text or "aktivitet" in text:
            # Try to extract JSON data
            json_match = re.search(r'allFutureActivities\s*:\s*(\[.*?\])', text, re.DOTALL)
            if json_match:
                try:
                    activities = json.loads(json_match.group(1))
                    for act in activities:
                        events.append({
                            "id": make_id(act.get("title", ""), "", "bmw"),
                            "name": act.get("title", ""),
                            "date": "",
                            "dateEnd": "",
                            "location": "Se länk",
                            "type": "Träff",
                            "organizer": "BMW MC-klubben",
                            "description": "",
                            "link": act.get("url", "https://www.bmwklubben.se/aktiviteter/"),
                            "region": "Sverige",
                            "source": "bmwklubben.se"
                        })
                except json.JSONDecodeError:
                    pass

    # Also look for activity cards in the HTML
    for card in soup.select("a.activity-card, a[href*='/aktiviteter/']"):
        title = card.get("title", "") or card.get_text(strip=True)
        href = card.get("href", "")
        if not title or title == "VISA FLER" or not href:
            continue

        full_url = href if href.startswith("http") else f"https://www.bmwklubben.se{href}"

        # Try to extract date from nearby elements
        day_el = card.select_one("[class*='day'], .display_day")
        month_el = card.select_one("[class*='month'], .display_month")

        events.append({
            "id": make_id(title, "", "bmw"),
            "name": title,
            "date": "",  # Hard to extract without JS rendering
            "dateEnd": "",
            "location": "Se länk",
            "type": detect_event_type(title),
            "organizer": "BMW MC-klubben",
            "description": "",
            "link": full_url,
            "region": "Sverige",
            "source": "bmwklubben.se"
        })

    # Remove events without dates (they're not useful)
    events = [e for e in events if e["date"]]

    print(f"  Extracted {len(events)} events from BMW HTML")
    return events


def scrape_mcparken():
    """
    Scrape MCparken calendar page.
    They have a simple HTML calendar at /pages/calendar/calendar-overview.aspx
    """
    print("Scraping MCparken (mcparken.se)...")
    url = "https://mcparken.se/pages/calendar/calendar-overview.aspx"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    events = []
    months_sv = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "maj": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "okt": "10", "nov": "11", "dec": "12"
    }

    # Find event blocks - they have a date badge and event title/link
    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        if "/calendar/" not in href or "calendar-overview" in href:
            continue

        title = link.get_text(strip=True)
        if not title or title in ("läs mer", "las mer"):
            continue

        # Get surrounding text for date/location
        parent = link.find_parent("div") or link.find_parent("li")
        if not parent:
            continue
        text = parent.get_text(" ", strip=True)

        # Extract date
        date_match = re.search(
            r'(\d{1,2})\s+(\w{3})\s*(?:-\s*(\d{1,2})\s+(\w{3}))?\s+(\d{4})',
            text
        )
        if not date_match:
            continue

        day = date_match.group(1).zfill(2)
        month = months_sv.get(date_match.group(2)[:3].lower(), "01")
        year = date_match.group(5)
        start_date = f"{year}-{month}-{day}"

        end_date = start_date
        if date_match.group(3) and date_match.group(4):
            end_day = date_match.group(3).zfill(2)
            end_month = months_sv.get(date_match.group(4)[:3].lower(), month)
            end_date = f"{year}-{end_month}-{end_day}"

        # Extract location
        loc_match = re.search(r'Var:\s*(.+?)(?:\d|med start|$)', text)
        location = loc_match.group(1).strip() if loc_match else ""

        full_url = f"https://mcparken.se{href}" if href.startswith("/") else href

        events.append({
            "id": make_id(title, start_date),
            "name": title,
            "date": start_date,
            "dateEnd": end_date,
            "location": location or "Se länk",
            "type": detect_event_type(title),
            "organizer": "Via MCparken",
            "description": title,
            "link": full_url,
            "region": guess_region(location),
            "source": "mcparken.se"
        })

    print(f"  Extracted {len(events)} events from MCparken")
    return events


# ---- Manual events (verified, always included) ----

def load_manual_events():
    """
    Manually curated events from organizer websites.
    These are verified events that cannot be auto-scraped easily.
    Updated by hand when new big events are announced.
    """
    print("Loading manually curated events...")
    return [
        {
            "id": "jonkoping-mcmassan-2026", "name": "MC-Mässan Jönköping (Elmia)",
            "date": "2026-01-23", "dateEnd": "2026-01-25",
            "location": "Elmiamässan, Jönköping", "type": "Mässa",
            "organizer": "MC-Mässan / Elmia",
            "description": "Sveriges största MC-mässa flyttar till Elmia. Nyheter, provkörningar, tillbehör och Customhoj Bike Show.",
            "link": "https://www.elmia.se/mcmassan/",
            "region": "Småland", "source": "elmia.se"
        },
        {
            "id": "halmstad-mcmassa-2026", "name": "MC-Mässan Halmstad",
            "date": "2026-03-07", "dateEnd": "2026-03-08",
            "location": "Halmstad Arena, Halmstad", "type": "Mässa",
            "organizer": "BVN Event / MC-Veteranerna",
            "description": "MC-mässa med utökat program. Stuntshow, utställare och klubbar.",
            "link": "https://www.bvnevent.se/",
            "region": "Halland", "source": "bvnevent.se"
        },
        {
            "id": "uppsala-mcmassa-2026", "name": "Uppsala MC-Mässa & Motorshow",
            "date": "2026-03-13", "dateEnd": "2026-03-15",
            "location": "Fyrishov, Uppsala", "type": "Mässa",
            "organizer": "BVN Event",
            "description": "Mässan fylls med motorcyklar, byggare, handlare, klubbar och mc-entusiaster.",
            "link": "https://www.bvnevent.se/Uppsala",
            "region": "Uppland", "source": "bvnevent.se"
        },
        {
            "id": "custom-motor-show-2026", "name": "Custom Motor Show",
            "date": "2026-04-03", "dateEnd": "2026-04-06",
            "location": "Elmia, Jönköping", "type": "Mässa",
            "organizer": "Elmia",
            "description": "Custom Motor Show med fokus på specialbyggda bilar och motorcyklar.",
            "link": "https://www.elmia.se/",
            "region": "Småland", "source": "elmia.se"
        },
        {
            "id": "adv-expo-2026", "name": "ADV Motorcycle Expo 2026",
            "date": "2026-04-18", "dateEnd": "2026-04-19",
            "location": "Upplands Väsby, Stockholms län", "type": "Mässa",
            "organizer": "Backroads AB / ADV Expo",
            "description": "Nordens största mässa för äventyrsmotorcyklister.",
            "link": "https://www.backroads.eu/adv-motorcycle-expo/",
            "region": "Stockholm", "source": "advmotorcycleexpo.com"
        },
        {
            "id": "custom-bikeshow-norrtalje-2026", "name": "Custom Bike Show Norrtälje",
            "date": "2026-06-06", "dateEnd": "2026-06-06",
            "location": "Norrtälje", "type": "Show",
            "organizer": "Custom Bike Show",
            "description": "Europas äldsta custom bike show. Choppers, bobbers, café racers.",
            "link": "https://www.custombikeshow.se/",
            "region": "Stockholm", "source": "custombikeshow.se"
        },
        {
            "id": "trollhattetraffen-2026", "name": "Trollhätteträffen",
            "date": "2026-06-05", "dateEnd": "2026-06-07",
            "location": "Ursands Camping, Trollhättan", "type": "Träff",
            "organizer": "SMC Västra Götaland",
            "description": "Stor MC-träff på nationaldagshelgen. Camping, livemusik och gemensamma utfärder.",
            "link": "https://www.svmc.se/",
            "region": "Västra Götaland", "source": "svmc.se"
        },
        {
            "id": "hojrock-2026", "name": "HojRock",
            "date": "2026-07-23", "dateEnd": "2026-07-26",
            "location": "Tånga Hed, Vårgårda", "type": "Fest",
            "organizer": "HojRock",
            "description": "En av Nordens största MC-träffar. Livemusik, camping och mc-gemenskap på Tånga Hed.",
            "link": "https://www.hojrock.se/",
            "region": "Västra Götaland", "source": "hojrock.se"
        },
        {
            "id": "vasteras-summermeet-2026", "name": "Västerås Summer Meet",
            "date": "2026-07-02", "dateEnd": "2026-07-04",
            "location": "Västerås", "type": "Show",
            "organizer": "Västerås Summer Meet",
            "description": "Stort bil- och mc-evenemang mitt i sommaren. Cruising, utställningar.",
            "link": "https://vasterassummermeet.se/",
            "region": "Västmanland", "source": "vasterassummermeet.se"
        },
        {
            "id": "malaren-runt-2026", "name": "Mälaren Runt",
            "date": "2026-08-16", "dateEnd": "2026-08-16",
            "location": "Mälardalen", "type": "Körning",
            "organizer": "SMC / Mälaren Runt",
            "description": "Sveriges största gemensamma MC-körning, 40:e gången!",
            "link": "https://www.svmc.se/club/maelaren-runt/",
            "region": "Mälardalen", "source": "svmc.se"
        },
        {
            "id": "gotland-ring-bikeweek-2026", "name": "Gotland Ring Bike Week",
            "date": "2026-07-03", "dateEnd": "2026-07-05",
            "location": "Gotland Ring, Gotland", "type": "Racing",
            "organizer": "Gotland Ring",
            "description": "Tre dagar på Gotlands racingbana. Bankörning och mc-festival.",
            "link": "https://www.alltommc.se/gotland-ring-bike-week-2026-early-bird-erbjudande/",
            "region": "Gotland", "source": "alltommc.se"
        },
        {
            "id": "american-days-2026", "name": "American Days",
            "date": "2026-06-04", "dateEnd": "2026-06-07",
            "location": "Sverige", "type": "Träff",
            "organizer": "VICS",
            "description": "American Days - träff för amerikanska mc-märken.",
            "link": "https://vics.se/kalender/",
            "region": "Sverige", "source": "vics.se"
        },
    ]


# ---- Deduplication ----

def dedup_key(event):
    """Create dedup key: normalized name + date"""
    name = event.get("name", "").lower().strip()
    date_str = event.get("date", "") or ""
    return f"{name}|{date_str}"


def deduplicate(all_events):
    """
    Remove duplicates. Priority: organizer's own site wins.
    """
    print(f"Deduplicating {len(all_events)} events...")

    source_priority = {
        # Organizer sites (highest priority)
        "hdcs.se": 1, "bmwklubben.se": 1, "hojrock.se": 1,
        "custombikeshow.se": 1, "vasterassummermeet.se": 1,
        "elmia.se": 1, "bvnevent.se": 1, "advmotorcycleexpo.com": 1,
        "vics.se": 1, "gwcs.se": 1, "gwef.eu": 1,
        # Federation sites
        "svmc.se": 2, "sulas.se": 2, "alltommc.se": 2,
        # Aggregators (lowest priority)
        "mcparken.se": 3, "bike.se": 3,
    }

    seen = {}
    for e in all_events:
        key = dedup_key(e)
        if key in seen:
            # Keep the one with higher priority (lower number)
            existing_priority = source_priority.get(seen[key].get("source", ""), 5)
            new_priority = source_priority.get(e.get("source", ""), 5)
            if new_priority < existing_priority:
                seen[key] = e
        else:
            seen[key] = e

    result = sorted(seen.values(), key=lambda e: e.get("date") or "9999-99-99")
    print(f"  After dedup: {len(result)} unique events")
    return result


# ---- Load/Save ----

def load_existing_events(filename=OUTPUT_FILE):
    """Load events from existing events.js, preserving manually added data"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'const EVENTS_DATA\s*=\s*(\{[\s\S]*\})\s*;', content)
        if not match:
            return []
        data = json.loads(match.group(1))
        events = data.get("events", [])
        print(f"  Loaded {len(events)} existing events from {filename}")
        return events
    except Exception as e:
        print(f"  Could not load existing events: {e}")
        return []


def write_events_js(events, filename=OUTPUT_FILE):
    """Write merged events to events.js"""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {"lastUpdated": now, "events": events}
    js = "const EVENTS_DATA = " + json.dumps(data, indent=2, ensure_ascii=False) + ";\n"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(js)

    print(f"\nWrote {len(events)} events to {filename}")
    print(f"Last updated: {now}")
    print(f"File size: {len(js) // 1024} KB")


# ---- Main ----

def main():
    print("=" * 60)
    print("  MC Kalendern Event Scraper")
    print(f"  Date: {TODAY}")
    print("=" * 60)

    all_events = []

    # 1. Load existing events (preserve what we have)
    existing = load_existing_events()
    all_events.extend(existing)

    # 2. Manual events (always included as baseline)
    all_events.extend(load_manual_events())

    # 3. Scrape H-DCS (WordPress REST API)
    try:
        all_events.extend(scrape_hdcs())
    except Exception as e:
        print(f"  ERROR scraping H-DCS: {e}")

    # 4. Scrape BMW MC-klubben
    try:
        all_events.extend(scrape_bmw_klubben())
    except Exception as e:
        print(f"  ERROR scraping BMW: {e}")

    # 5. Scrape MCparken
    try:
        all_events.extend(scrape_mcparken())
    except Exception as e:
        print(f"  ERROR scraping MCparken: {e}")

    # 6. Deduplicate and sort
    unique_events = deduplicate(all_events)

    # 7. Write output
    write_events_js(unique_events)

    # 8. Stats
    sources = {}
    types = {}
    regions = {}
    for e in unique_events:
        sources[e.get("source", "?")] = sources.get(e.get("source", "?"), 0) + 1
        types[e.get("type", "?")] = types.get(e.get("type", "?"), 0) + 1
        regions[e.get("region", "?")] = regions.get(e.get("region", "?"), 0) + 1

    print("\nBy source:")
    for s, c in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")

    print("\nBy type:")
    for t, c in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {c}")

    print("\nTop 10 regions:")
    for r, c in sorted(regions.items(), key=lambda x: -x[1])[:10]:
        print(f"  {r}: {c}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
