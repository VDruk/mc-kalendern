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
    "överhärde": "Gävleborg", "söderhamn": "Gävleborg",
    "borgeby": "Skåne",
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
    if any(w in t for w in ["tur", "körning", "ride", "mc-tur", "utflykt", "on bike", "dagstur", "bussresa"]):
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


# ---- Location enrichment ----

# Known Swedish places to match in event names/descriptions
KNOWN_PLACES = {
    "stockholm": "Stockholm", "malmö": "Malmö", "göteborg": "Göteborg",
    "kristianstad": "Kristianstad", "hedemora": "Hedemora", "falun": "Falun",
    "linköping": "Linköping", "norrtälje": "Norrtälje", "ekerö": "Ekerö",
    "öland": "Öland", "bornholm": "Bornholm, Danmark", "surahammar": "Surahammar",
    "markaryd": "Markaryd", "hovmantorp": "Hovmantorp", "växjö": "Växjö",
    "bankeryd": "Bankeryd", "staffanstorp": "Staffanstorp", "ljungby": "Ljungby",
    "kristianopel": "Kristianopel", "eringsboda": "Eringsboda", "alstermo": "Alstermo",
    "moheda": "Moheda", "oskarshamn": "Oskarshamn", "värnamo": "Värnamo",
    "trollhättan": "Trollhättan", "östersund": "Östersund", "motala": "Motala",
    "fredericia": "Fredericia, Danmark", "kinnekulle": "Kinnekulle",
    "falkenberg": "Falkenberg", "bromölla": "Bromölla", "vollsjö": "Vollsjö",
    "tiveden": "Tiveden", "dalsland": "Dalsland", "sikhall": "Sikhall",
    "rådis": "Rådis, Dalarna", "babel": "Babel, Stockholm",
    "probike malmö": "Probike, Malmö",
}

# BMW district prefix -> region
BMW_DISTRICT_LOCATIONS = {
    "D1": "Norrbotten", "D2": "Västerbotten", "D3": "Västernorrland",
    "D4": "Dalarna", "D5": "Västmanland", "D6": "Värmland",
    "D7": "Stockholm", "D8": "Västra Götaland", "D9": "Östergötland",
    "D10": "Västra Götaland", "D11": "Småland", "D12": "Halland",
    "D14": "Jönköping", "D15": "Skåne",
}

# HDCS district prefix -> region
HDCS_DISTRICT_LOCATIONS = {
    "DOA": "Stockholm", "DOB": "Skåne", "DO-C": "Halland/VGötaland",
    "DOE": "Småland", "DOG": "Dalarna", "DOH": "Västerbotten",
    "DO-I": "Västernorrland", "DKB": "Blekinge", "LOB": "Skåne",
    "LOD": "Västra Götaland",
}


def enrich_location(event):
    """
    Try to determine a real location for events with 'Se länk' or empty location.
    Uses event name, description, source, and district patterns.
    Returns the enriched location string, or the original if no match found.
    """
    loc = (event.get("location") or "").strip()
    if loc.lower() not in ("se länk", "se lank", "", "tbd"):
        return loc  # Already has a location

    name = event.get("name", "")
    desc = event.get("description", "")
    source = event.get("source", "")
    text = f"{name} {desc}".lower()

    # 1. Check for online/digital events
    if any(w in text for w in ["teams", "digitalt", "zoom", "online", "webinar"]):
        return "Online / Digitalt"

    # 2. Try "från <City>" pattern in name
    m = re.search(r'från\s+([A-ZÅÄÖ][a-zåäö]+(?:\s+[A-ZÅÄÖ][a-zåäö]+)?)', name)
    if m:
        return m.group(1)

    # 3. Try known places in name/description
    for key, city in KNOWN_PLACES.items():
        if key in text:
            return city

    # 4. BMW district prefix
    if source == "bmwklubben.se":
        m = re.match(r'(D\d+)\b', name)
        if m and m.group(1) in BMW_DISTRICT_LOCATIONS:
            return BMW_DISTRICT_LOCATIONS[m.group(1)]
        if "region väst" in name.lower():
            return "Västra Götaland"

    # 5. HDCS district prefix
    if source == "hdcs.se":
        for prefix, region in HDCS_DISTRICT_LOCATIONS.items():
            if name.startswith(prefix + " ") or name.startswith(prefix + "-"):
                return region

    # 6. Fallback: keep original (will show as "Se länk")
    return loc or "Sverige"


def enrich_all_locations(events):
    """Run location enrichment on all events, fix 'Se länk' locations."""
    fixed = 0
    for e in events:
        old_loc = e.get("location", "")
        new_loc = enrich_location(e)
        if new_loc != old_loc:
            e["location"] = new_loc
            fixed += 1
    if fixed:
        print(f"  Location enrichment: fixed {fixed} events")
    return events


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
    Scrape BMW MC-klubben via their admin-ajax.php endpoint.
    The site uses Alpine.js with loadMorePosts which calls:
    POST /wp-admin/admin-ajax.php with action=load_more_posts
    Returns JSON with full event data including dates, addresses, districts.
    """
    print("Scraping BMW MC-klubben (bmwklubben.se)...")
    events = []

    url = "https://www.bmwklubben.se/wp-admin/admin-ajax.php"
    payload = {
        "action": "load_more_posts",
        "post_type": "product",
        "display_selection": "upcoming",
        "offset": "0",
        "posts_per_page": "500",
    }

    try:
        r = requests.post(url, data=payload, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  WARN: BMW AJAX failed: {e}")
        return []

    posts = data.get("posts", [])
    if not posts:
        print("  WARN: No BMW events returned")
        return []

    print(f"  Found {len(posts)} events from BMW AJAX")

    # District name -> region mapping
    district_map = {
        "D1": "Norrbotten", "D2": "Västerbotten", "D3": "Västernorrland",
        "D4": "Dalarna", "D5": "Västmanland", "D6": "Värmland",
        "D7": "Stockholm", "D8": "Västra Götaland", "D9": "Östergötland",
        "D10": "Västra Götaland", "D11": "Småland", "D12": "Halland",
        "D14": "Jönköping", "D15": "Skåne",
    }

    for post in posts:
        title = clean_html(post.get("title", ""))
        if not title:
            continue

        # Date from date_time field (format: "2026-03-12 18:30")
        date_time = post.get("date_time") or post.get("start_date") or ""
        date_time_end = post.get("date_time_end") or post.get("end_date") or ""

        start = date_time[:10] if date_time else ""
        end = date_time_end[:10] if date_time_end else start

        if not start:
            continue  # Skip events without dates

        # Location from address field (full address) or city
        address = post.get("address") or ""
        city = post.get("city") or ""

        # Clean up address: remove postal code and country for shorter display
        location = address or city
        if location:
            # Shorten "Agnesfridsvägen 119, 213 75 Malmö, Sverige" -> "Agnesfridsvägen 119, Malmö"
            location = re.sub(r',?\s*\d{3}\s*\d{2}\s*', ', ', location)
            location = re.sub(r',?\s*Sverige\s*$', '', location)
            location = re.sub(r',\s*,', ',', location).strip(', ')

        # Region from districts
        region = "Sverige"
        districts = post.get("districts") or []
        if isinstance(districts, list):
            for d in districts:
                d_name = d.get("name", "") if isinstance(d, dict) else str(d)
                # Match "D15" etc from district name
                d_match = re.match(r'(D\d+)', d_name)
                if d_match and d_match.group(1) in district_map:
                    region = district_map[d_match.group(1)]
                    break
        elif isinstance(districts, str):
            d_match = re.match(r'(D\d+)', districts)
            if d_match and d_match.group(1) in district_map:
                region = district_map[d_match.group(1)]

        # Build URL
        link = post.get("url", "")
        if not link:
            link = "https://www.bmwklubben.se/aktiviteter/"

        desc = clean_html(post.get("preamble") or post.get("excerpt") or "")

        events.append({
            "id": make_id(title, start, "bmw"),
            "name": title,
            "date": start,
            "dateEnd": end,
            "location": location[:150] or "Se länk",
            "type": detect_event_type(title),
            "organizer": "BMW MC-klubben",
            "description": desc or title,
            "link": link,
            "region": region,
            "source": "bmwklubben.se"
        })

    print(f"  Extracted {len(events)} events from BMW MC-klubben")
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


def scrape_gwcs():
    """
    Scrape GWCS (GoldWing Club Sweden) calendar.
    They use The Events Calendar on WordPress but REST API is disabled (404).
    We scrape the traffkalendern page HTML and extract specific event URLs
    from the "Visa detaljer" links (a[href*="/events/"]).
    URL format: gwcs.se/events/{slug}/?occurrence={date}
    """
    print("Scraping GWCS (gwcs.se)...")
    url = "https://gwcs.se/traffkalendern/"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    events = []
    months_sv = {
        "januari": "01", "februari": "02", "mars": "03", "april": "04",
        "maj": "05", "juni": "06", "juli": "07", "augusti": "08",
        "september": "09", "oktober": "10", "november": "11", "december": "12"
    }

    # Find all "Visa detaljer" links which point to specific event pages
    # These are the a[href*="/events/"] links on the calendar page
    event_links = soup.select('a[href*="/events/"]')

    for link_el in event_links:
        href = link_el.get("href", "")
        if not href or href.endswith("/events/"):
            continue

        # Extract occurrence date from URL: ?occurrence=2026-03-15
        occ_match = re.search(r'occurrence=(\d{4}-\d{2}-\d{2})', href)
        start_date = occ_match.group(1) if occ_match else ""

        # Walk up the DOM to find the event container and extract title/venue
        parent = link_el.parent
        for _ in range(5):
            if parent and parent.parent:
                parent = parent.parent
            else:
                break

        if not parent:
            continue

        text = parent.get_text(" ", strip=True)

        # Extract title: the text between weekday name and venue/link
        # Pattern in text: "15 mars söndag Sörmlandswingarnas fikaträff Sigridslunds Café | Årdala Visa detaljer"
        title = ""
        venue = ""

        # Find title from heading or link text before "Visa detaljer"
        title_el = None
        for heading in parent.select("h2, h3, h4, strong, b"):
            t = heading.get_text(strip=True)
            if t and len(t) > 3 and t != "Visa detaljer":
                title_el = heading
                break

        if title_el:
            title = title_el.get_text(strip=True)
        else:
            # Try to extract from text: everything after weekday, before "|" or "Visa"
            m = re.search(
                r'(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)\s+(.+?)(?:\s*\||\s*Visa)',
                text, re.IGNORECASE
            )
            if m:
                title = m.group(1).strip()

        if not title:
            continue

        # Extract venue: text after "|" before "Visa detaljer"
        venue_match = re.search(r'\|\s*(.+?)\s*Visa\s+detaljer', text, re.IGNORECASE)
        if venue_match:
            venue = venue_match.group(1).strip()

        # If no occurrence date, try to extract from surrounding text
        if not start_date:
            for month_name, month_num in months_sv.items():
                day_m = re.search(r'(\d{1,2})\s*' + month_name, text.lower())
                if day_m:
                    start_date = f"{YEAR}-{month_num}-{day_m.group(1).zfill(2)}"
                    break

        if not start_date:
            continue

        # Build full URL
        full_url = href if href.startswith("http") else f"https://gwcs.se{href}"

        events.append({
            "id": make_id(title, start_date, "gwcs"),
            "name": title,
            "date": start_date,
            "dateEnd": start_date,  # Single-day events (multi-day have it in title)
            "location": venue or title,  # Use title as fallback (often contains venue)
            "type": detect_event_type(title),
            "organizer": "GoldWing Club Sweden",
            "description": title,
            "link": full_url,
            "region": guess_region(venue or title),
            "source": "gwcs.se"
        })

    # Deduplicate by URL (same event can appear in multiple parent containers)
    seen_urls = {}
    unique_events = []
    for e in events:
        if e["link"] not in seen_urls:
            seen_urls[e["link"]] = True
            unique_events.append(e)

    print(f"  Extracted {len(unique_events)} events from GWCS")
    return unique_events


def scrape_mchk():
    """
    Scrape MCHK (Motorcykelhistoriska Klubben) events from mchk.org.
    They have a plain calendar page with events listed as contentgroup widgets.
    Each heading follows the pattern: "date - MCHK Chapter - EventType"
    Body text contains location details (Plats: ..., addresses, etc.)
    """
    print("Scraping MCHK (mchk.org)...")
    url = "https://mchk.org/evenemang/kalender-34490789"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    months_sv = {
        "januari": "01", "februari": "02", "mars": "03", "april": "04",
        "maj": "05", "juni": "06", "juli": "07", "augusti": "08",
        "september": "09", "oktober": "10", "november": "11", "december": "12"
    }

    # MCHK chapter -> region mapping
    mchk_regions = {
        "stockholm": "Stockholm", "gävleborg": "Gävleborg",
        "närke": "Närke", "gotland": "Gotland",
        "skaraborg": "Västra Götaland", "syd": "Skåne",
        "mälardalen": "Västmanland",
    }

    # Find all contentgroup widgets (each is an event)
    groups = soup.select(".widget__contentgroup")

    for g in groups:
        heading_el = g.select_one(".contentgroup__heading, h2, h3")
        body_el = g.select_one(".contentgroup__body")

        if not heading_el:
            continue

        heading = re.sub(r'\s+', ' ', heading_el.get_text(strip=True))

        # Match heading pattern: "25 februari - MCHK Gävleborg - Årsmöte"
        # or multi-day: "22 - 29 april - bussresa till England"
        # or "13-16 juni - Trondhjemsridtet"
        m = re.match(
            r'(\d{1,2})(?:\s*-\s*(\d{1,2}))?\s+'
            r'(januari|februari|mars|april|maj|juni|juli|augusti|september|oktober|november|december)'
            r'\s*-\s*(.*)',
            heading, re.IGNORECASE
        )
        if not m:
            continue

        day_start = m.group(1).zfill(2)
        day_end = m.group(2)
        month_name = m.group(3).lower()
        rest = m.group(4).strip()
        month_num = months_sv.get(month_name, "01")

        start_date = f"{YEAR}-{month_num}-{day_start}"
        if day_end:
            end_date = f"{YEAR}-{month_num}-{day_end.zfill(2)}"
        else:
            end_date = start_date

        # Parse title: usually "MCHK Chapter - EventType" or just event name
        title = rest
        chapter = ""
        chapter_match = re.match(
            r'MCHK\s*(?:-\s*)?([\wåäöÅÄÖ]+(?:\s+[\wåäöÅÄÖ]+)?)\s*-\s*(.*)',
            rest
        )
        if chapter_match:
            chapter = chapter_match.group(1).strip()
            event_name_part = chapter_match.group(2).strip()
            title = f"MCHK {chapter}: {event_name_part}"
        elif rest.startswith("MCHK"):
            title = rest

        # Get description text
        desc = ""
        if body_el:
            desc = re.sub(r'\s+', ' ', body_el.get_text(strip=True))

        # Extract location from description
        location = ""

        # Extract location from description
        location = ""

        # Pattern 1: "Plats: <location>" or "Plats <Venue>"
        plats_m = re.search(
            r'[Pp]lats:?\s+([A-ZÅÄÖ][\wåäöÅÄÖ\s,\-]+?)(?:\s+tid\b|\s+kl[\s.]|\.?\s+[A-ZÅÄÖ]|\.\s|\s*$)',
            desc
        )
        if plats_m:
            location = plats_m.group(1).strip().rstrip('.,;')

        # Pattern 2: "i klubblokalen <address>" or "på museet <name>"
        if not location:
            loc_m = re.search(
                r'(?:i klubblokalen|på museet|på plats på kansliet,?|Jakobsbergs gård)\s*([^.]{3,80})',
                desc
            )
            if loc_m:
                location = loc_m.group(0).strip()

        # Pattern 3: Street address pattern (e.g. "Martallsgatan i Visby")
        if not location:
            addr_m = re.search(
                r'([A-ZÅÄÖ][\wåäöÅÄÖ]*(?:gatan|vägen|allén|gård|slott)'
                r'(?:\s+\d+(?:\s*-\s*\d+)?)?'
                r'(?:\s+i\s+[\wåäöÅÄÖ]+)?'
                r'(?:,\s*[\wåäöÅÄÖ]+)?)',
                desc
            )
            if addr_m:
                location = addr_m.group(1).strip()

        # Pattern 4: City from desc (e.g. "Örebro", "Götene", "Visby")
        if not location and desc:
            for city_key in sorted(CITY_REGIONS.keys(), key=len, reverse=True):
                if city_key in desc.lower():
                    location = city_key.capitalize()
                    break

        # Pattern 5: City from event name (e.g. "bussresa till Söderhamn")
        if not location:
            till_m = re.search(r'till\s+([A-ZÅÄÖ][\wåäöÅÄÖ]+)', title)
            if till_m:
                location = till_m.group(1)

        # Pattern 6: Use chapter name as fallback region hint
        if not location and chapter:
            ch_lower = chapter.lower()
            if ch_lower in mchk_regions:
                location = mchk_regions[ch_lower]

        # Determine region
        region = "Sverige"
        if chapter:
            ch_lower = chapter.lower()
            if ch_lower in mchk_regions:
                region = mchk_regions[ch_lower]
        if region == "Sverige" and location:
            region = guess_region(location)

        # Clean up location: truncate if too long
        if len(location) > 80:
            # Try to cut at comma
            short = location[:80]
            if ',' in short:
                short = short.rsplit(',', 1)[0]
            location = short.strip()

        events.append({
            "id": make_id(title, start_date, "mchk"),
            "name": title,
            "date": start_date,
            "dateEnd": end_date,
            "location": location or "Sverige",
            "type": detect_event_type(title, desc[:100]),
            "organizer": f"MCHK{' ' + chapter if chapter else ''}",
            "description": (desc or title)[:250],
            "link": "https://mchk.org/evenemang/kalender-34490789",
            "region": region,
            "source": "mchk.org"
        })

    print(f"  Extracted {len(events)} events from MCHK")
    return events


def scrape_oamck():
    """
    Scrape ÖAMCK (Östra Aros MCK) events from oamck.se.
    They use The Events Calendar with Schema.org JSON-LD structured data
    embedded in the page. Each event has full details: name, date, URL,
    location, and organizer.

    We skip:
    - Weekly "Fikakväll i klubbkåken" (too frequent, internal club meetings)
    - Foreign trips (Andalusien etc.)
    """
    print("Scraping ÖAMCK (oamck.se)...")
    url = "https://oamck.se/events/"
    r = safe_get(url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    events = []

    # Extract Schema.org JSON-LD event data
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get("@type") != "Event":
                    continue

                name = clean_html(item.get("name", ""))
                if not name:
                    continue

                # Skip weekly fikakväll (too many, very internal)
                if "fikakväll" in name.lower() or "fikakvall" in name.lower():
                    continue

                # Skip foreign trips
                name_lower = name.lower()
                if any(w in name_lower for w in ["andalusien", "italien", "spanien"]):
                    continue

                start_raw = item.get("startDate", "")
                end_raw = item.get("endDate", "")
                start = start_raw[:10] if start_raw else ""
                end = end_raw[:10] if end_raw else start

                if not start:
                    continue

                event_url = item.get("url", "")

                # Location from structured data
                loc_data = item.get("location", {})
                location = ""
                if isinstance(loc_data, dict):
                    loc_name = loc_data.get("name", "")
                    loc_addr = loc_data.get("address", {})
                    if isinstance(loc_addr, dict):
                        loc_city = loc_addr.get("addressLocality", "")
                        location = ", ".join(filter(None, [loc_name, loc_city]))
                    else:
                        location = loc_name

                # Organizer
                org_data = item.get("organizer", {})
                organizer = "ÖAMCK"
                if isinstance(org_data, dict):
                    organizer = org_data.get("name", "ÖAMCK")

                events.append({
                    "id": make_id(name, start, "oamck"),
                    "name": name,
                    "date": start,
                    "dateEnd": end,
                    "location": location or "Uppsala",
                    "type": detect_event_type(name),
                    "organizer": organizer,
                    "description": name,
                    "link": event_url or "https://oamck.se/events/",
                    "region": guess_region(location or "Uppsala"),
                    "source": "oamck.se"
                })
        except (json.JSONDecodeError, KeyError):
            continue

    print(f"  Extracted {len(events)} events from ÖAMCK")
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
        "vics.se": 1, "gwcs.se": 1, "gwef.eu": 1, "oamck.se": 1,
        "mchk.org": 1,
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


TYPE_NORMALIZE = {
    "Traff": "Träff", "traff": "Träff",
    "Korning": "Körning", "korning": "Körning",
    "Massa": "Mässa", "massa": "Mässa",
    "Tur": "Tur", "Racing": "Racing", "Show": "Show",
    "Fest": "Fest", "Trackday": "Trackday",
}

ORG_NORMALIZE = {
    "Harley-Davidson Club Sweden": "H-DCS",
}

def write_events_js(events, filename=OUTPUT_FILE):
    """Write merged events to events.js"""
    for e in events:
        e["type"] = TYPE_NORMALIZE.get(e.get("type", ""), e.get("type", "Träff"))
        e["organizer"] = ORG_NORMALIZE.get(e.get("organizer", ""), e.get("organizer", ""))
        if not e.get("dateEnd"):
            e["dateEnd"] = e.get("date", "")
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

    # 6. Scrape GWCS
    try:
        all_events.extend(scrape_gwcs())
    except Exception as e:
        print(f"  ERROR scraping GWCS: {e}")

    # 7. Scrape ÖAMCK
    try:
        all_events.extend(scrape_oamck())
    except Exception as e:
        print(f"  ERROR scraping ÖAMCK: {e}")

    # 8. Scrape MCHK
    try:
        all_events.extend(scrape_mchk())
    except Exception as e:
        print(f"  ERROR scraping MCHK: {e}")

    # 9. Deduplicate and sort
    unique_events = deduplicate(all_events)

    # 10. Enrich locations (fix "Se länk" using name/district patterns)
    unique_events = enrich_all_locations(unique_events)

    # 11. Write output
    write_events_js(unique_events)

    # 12. Stats
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
