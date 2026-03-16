#!/usr/bin/env python3
"""
FB Event Tool for MC Kalendern
===============================
Extracts event data from Facebook event pages and checks for duplicates
against events.js.

Requirements:
  pip install selenium undetected-chromedriver requests beautifulsoup4

Usage:
  python fb-event-tool.py extract <url>              # Extract one event
  python fb-event-tool.py extract <url1> <url2> ...  # Extract multiple
  python fb-event-tool.py batch <file.txt>            # URLs from file (one per line)
  python fb-event-tool.py check-new <file.txt>        # Extract + dedup against events.js

Options:
  --no-browser       Skip Selenium, use requests only (limited data)
  --download-images  Download cover images to ads/ folder
  --events-js PATH   Path to events.js (default: ../events.js)
  --output FILE      Write JSON output to file instead of stdout
  --headless         Run Chrome in headless mode (default: visible)
  --add              Add new events directly to events.js (Type 1 card)
  --back-image PATH  Path to back image (e.g. ads/my-event-back-2026-05-16.jpg)

Examples:
  python fb-event-tool.py extract https://www.facebook.com/events/1267483558130059/
  python fb-event-tool.py extract "https://fb.com/events/123" --add --back-image ads/event-back-2026-05-16.jpg
  python fb-event-tool.py batch urls.txt --download-images
  python fb-event-tool.py check-new urls.txt --events-js ../events.js
"""

import argparse
import json
import os
import re
import sys
import time
import hashlib
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

# Optional imports - graceful fallback
try:
    import undetected_chromedriver as uc
    HAS_UC = True
except ImportError:
    HAS_UC = False

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException
    HAS_SELENIUM = True
except ImportError:
    HAS_SELENIUM = False

try:
    import requests
    from bs4 import BeautifulSoup
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# =============================================================================
# Constants
# =============================================================================

SCRIPT_DIR = Path(__file__).parent
DEFAULT_EVENTS_JS = SCRIPT_DIR.parent / "events.js"
DEFAULT_ADS_DIR = SCRIPT_DIR.parent / "ads"

# Swedish MC event type mapping
TYPE_KEYWORDS = {
    "Traff": ["traff", "mote", "moete", "meetup", "meet", "fika", "oppet hus",
              "manadsmoete", "klubb", "samling", "jubileum", "firar", "arsfest",
              "medlems"],
    "Korning": ["korning", "tur", "ride", "avrostning", "roadtrip", "mc-tur",
                "nationaldags", "kvallskorning", "poker run", "pokerrun",
                "rundan", "runt"],
    "Show": ["show", "utstaellning", "lansering", "provkorning", "provkor",
             "demo", "expo", "messa", "massan", "marknad", "invigning",
             "butik", "showroom", "modell", "nyhet"],
    "Fest": ["fest", "party", "bikerfest", "natt", "night", "grillfest",
             "konsert", "musik", "band", "scen"],
    "Racing": ["racing", "race", "speedway", "motocross", "enduro",
               "roadracing", "dragrace", "tjanstekorning", "traning"],
}

# Valid event types (with correct Swedish characters)
VALID_TYPES = {"Träff", "Körning", "Show", "Fest", "Racing"}

# Swedish month names for date parsing
SV_MONTHS = {
    "januari": 1, "februari": 2, "mars": 3, "april": 4,
    "maj": 5, "juni": 6, "juli": 7, "augusti": 8,
    "september": 9, "oktober": 10, "november": 11, "december": 12,
}

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# 21 SMC regions
VALID_REGIONS = [
    "Blekinge", "Dalarna", "Gotland", "Gavleborg", "Halland",
    "Jamtland", "Jonkoping", "Kalmar", "Kronoberg", "Norrbotten",
    "Skane", "Stockholm", "Sodermanland", "Uppsala", "Varmland",
    "Vasterbotten", "Vasternorrland", "Vastmanland",
    "Vastra Gotaland", "Orebro", "Ostergotland",
]

# City to region mapping (common Swedish MC cities)
CITY_REGION_MAP = {
    "stockholm": "Stockholm", "solna": "Stockholm", "sundbyberg": "Stockholm",
    "upplands vasby": "Stockholm", "upplands-vasby": "Stockholm",
    "jarfalla": "Stockholm", "nacka": "Stockholm", "huddinge": "Stockholm",
    "sodertalje": "Stockholm", "botkyrka": "Stockholm", "haninge": "Stockholm",
    "tungelsta": "Stockholm", "taby": "Stockholm", "vallentuna": "Stockholm",
    "norrtalje": "Uppsala", "norrtaelje": "Uppsala",
    "goteborg": "Vastra Gotaland", "gothenburg": "Vastra Gotaland",
    "malmo": "Skane", "helsingborg": "Skane", "lund": "Skane",
    "kristianstad": "Skane",
    "uppsala": "Uppsala", "enkoping": "Uppsala",
    "vasteras": "Vastmanland", "sala": "Vastmanland",
    "orebro": "Orebro", "karlskoga": "Orebro", "odensbacken": "Orebro",
    "kumla": "Orebro", "hallsberg": "Orebro", "degerfors": "Orebro",
    "linkoping": "Ostergotland", "norrkoping": "Ostergotland",
    "motala": "Ostergotland",
    "jonkoping": "Jonkoping", "huskvarna": "Jonkoping",
    "vaxjo": "Kronoberg", "ljungby": "Kronoberg",
    "kalmar": "Kalmar", "oskarshamn": "Kalmar", "monsteras": "Kalmar", "monesteras": "Kalmar",
    "karlskrona": "Blekinge", "ronneby": "Blekinge",
    "halmstad": "Halland", "falkenberg": "Halland", "varberg": "Halland",
    "karlstad": "Varmland", "sunne": "Varmland",
    "gavle": "Gavleborg", "sandviken": "Gavleborg",
    "sundsvall": "Vasternorrland", "harnosand": "Vasternorrland",
    "ostersund": "Jamtland", "are": "Jamtland",
    "umea": "Vasterbotten", "skelleftea": "Vasterbotten",
    "lulea": "Norrbotten", "kiruna": "Norrbotten",
    "falun": "Dalarna", "borlange": "Dalarna", "mora": "Dalarna",
    "visby": "Gotland",
    "nykoping": "Sodermanland", "eskilstuna": "Sodermanland",
    "balsta": "Uppsala", "sigtuna": "Stockholm", "marsta": "Stockholm",
    "ekero": "Stockholm", "lidingo": "Stockholm",
    "sollentuna": "Stockholm", "bromma": "Stockholm", "kista": "Stockholm",
    "tyreso": "Stockholm", "varmdo": "Stockholm", "osteraker": "Stockholm",
    "nynashamn": "Stockholm", "gustavsberg": "Stockholm",
    "strangnas": "Sodermanland", "katrineholm": "Sodermanland",
    "trollhattan": "Vastra Gotaland", "boras": "Vastra Gotaland",
    "skovde": "Vastra Gotaland", "lidkoping": "Vastra Gotaland",
    "uddevalla": "Vastra Gotaland", "kungalv": "Vastra Gotaland",
    "alingsas": "Vastra Gotaland", "mariestad": "Vastra Gotaland",
    "vetlanda": "Jonkoping", "nassjo": "Jonkoping",
    "vastervik": "Kalmar", "nybro": "Kalmar",
    "landskrona": "Skane", "trelleborg": "Skane", "ystad": "Skane",
    "simrishamn": "Skane", "angelholm": "Skane", "hassleholm": "Skane",
    "karlshamn": "Blekinge", "solvesborg": "Blekinge",
    "arvika": "Varmland", "kristinehamn": "Varmland",
    "hudiksvall": "Gavleborg", "soderhamn": "Gavleborg",
    "ornskoldsvik": "Vasternorrland", "kramfors": "Vasternorrland",
    "gallivare": "Norrbotten", "boden": "Norrbotten", "pitea": "Norrbotten",
    "avesta": "Dalarna", "ludvika": "Dalarna", "rattvik": "Dalarna",
    "tierp": "Uppsala", "osthammar": "Uppsala",
    "koping": "Vastmanland", "fagersta": "Vastmanland",
    "mjolby": "Ostergotland", "finspang": "Ostergotland",
    "laholm": "Halland", "kungsbacka": "Halland",
}


# =============================================================================
# Browser Setup
# =============================================================================

def create_driver(headless=True):
    """Create a Chrome/Chromium driver for scraping.
    Uses a clean Chrome profile (no login needed, FB public events are visible).
    """
    common_args = [
        "--no-sandbox",
        "--disable-dev-shm-usage",
        "--window-size=1280,900",
        "--lang=en-US",
    ]

    # Try regular Selenium (has built-in selenium-manager for version matching)
    if HAS_SELENIUM:
        try:
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            for arg in common_args:
                options.add_argument(arg)
            driver = webdriver.Chrome(options=options)
            print("  Using: Selenium (regular)")
            return driver
        except Exception as e:
            print(f"  [!] Selenium failed: {e}")

    print("[!] No working Chrome driver found.")
    print("    Make sure Chrome is installed and up to date.")
    print("    pip install selenium")
    return None


# =============================================================================
# Facebook Page Extraction
# =============================================================================

def extract_with_browser(url, driver):
    """Extract event data from a Facebook event page using Selenium."""
    print(f"  Loading: {url}")
    driver.get(url)
    time.sleep(5)  # Wait for FB to render

    # Click ALL "See more" buttons to expand description
    # FB uses various DOM structures, so we try multiple strategies
    see_more_clicked = 0

    # Strategy 1: XPath with role='button' and text
    strategies = [
        "//div[@role='button'][contains(text(), 'See more')]",
        "//div[@role='button'][contains(text(), 'Se mer')]",
        "//span[contains(text(), 'See more')]/ancestor::div[@role='button']",
        "//div[contains(@class, 'see_more')]//*[@role='button']",
    ]
    for xpath in strategies:
        try:
            btns = driver.find_elements(By.XPATH, xpath)
            for btn in btns[:3]:
                try:
                    driver.execute_script("arguments[0].click();", btn)
                    see_more_clicked += 1
                    time.sleep(1)
                except Exception:
                    pass
        except Exception:
            pass

    # Strategy 2: JavaScript - find and click all "See more" elements
    if see_more_clicked == 0:
        try:
            clicked = driver.execute_script("""
                let clicked = 0;
                // Find all elements containing "See more" text
                const walker = document.createTreeWalker(
                    document.body, NodeFilter.SHOW_TEXT, null, false);
                const nodes = [];
                while (walker.nextNode()) {
                    if (walker.currentNode.textContent.trim() === 'See more' ||
                        walker.currentNode.textContent.trim() === 'Se mer') {
                        nodes.push(walker.currentNode.parentElement);
                    }
                }
                for (const el of nodes) {
                    // Walk up to find clickable parent
                    let target = el;
                    for (let i = 0; i < 5; i++) {
                        if (target.getAttribute('role') === 'button' ||
                            target.tagName === 'A' ||
                            target.onclick) {
                            target.click();
                            clicked++;
                            break;
                        }
                        target = target.parentElement;
                        if (!target) break;
                    }
                }
                return clicked;
            """)
            see_more_clicked += (clicked or 0)
        except Exception:
            pass

    if see_more_clicked > 0:
        print(f"  Expanded {see_more_clicked} 'See more' section(s)")
        time.sleep(2)  # Wait for content to load after clicking
    else:
        print("  [i] No 'See more' buttons found (description may be truncated)")

    # Get all page text
    body_text = driver.find_element(By.TAG_NAME, "body").text
    title_raw = driver.title

    # Parse the extracted text
    return parse_fb_event_text(body_text, title_raw, url)


def parse_fb_event_text(body_text, title_raw, url):
    """Parse Facebook event page text into structured data."""
    event = {
        "url": url,
        "source": "facebook.com",
    }

    # 1. Title from page title
    title = re.sub(r'^\(\d+\)\s*', '', title_raw)
    title = re.sub(r'\s*\|\s*Facebook$', '', title)
    title = title.replace('\\', '')  # Remove any backslash escaping
    title = title.strip()
    event["name_raw"] = title
    event["name"] = clean_event_title(title)

    # 2. Find Details section
    details_idx = body_text.find("Details")
    if details_idx > -1:
        details_section = body_text[details_idx:details_idx + 4000]
        lines = [l.strip() for l in details_section.split('\n') if l.strip()]

        # Parse organizer: "Event by <name>"
        for line in lines[:5]:
            m = re.match(r'Event by (.+)', line)
            if m:
                event["organizer"] = m.group(1).strip()
                break

        # Parse address: look for location patterns in Details section
        # Strategy: check multiple patterns, from most specific to least
        organizer_idx = -1
        for i, line in enumerate(lines[:8]):
            if line.startswith('Event by'):
                organizer_idx = i
                break

        # Pattern 1: Line with Swedish postal code (123 45) + Sweden/Sverige
        for line in lines[:10]:
            if re.search(r'\d{3}\s?\d{2}', line) and ('Sweden' in line or 'Sverige' in line or ',' in line):
                event["location_raw"] = line.strip()
                break
        # Pattern 2: Line with comma + digits (street, postal)
        if "location_raw" not in event:
            for line in lines[:10]:
                if re.search(r', \d{3}', line) and not line.startswith('Event by'):
                    event["location_raw"] = line.strip()
                    break
        # Pattern 3: Line right after organizer that looks like an address
        # (contains a comma, or a street word like "väg", "gatan", "gata", "vägen")
        if "location_raw" not in event and organizer_idx >= 0:
            for line in lines[organizer_idx + 1:organizer_idx + 4]:
                if line.startswith('Event by') or line.startswith('Details'):
                    continue
                line_lower = line.lower()
                # Check if it looks like a location (has comma, or street indicator, or city name)
                is_addr = (',' in line or
                           re.search(r'(väg|gatan|gata|vägen|torget|plats|stigen|allé)', line_lower) or
                           re.search(r'(v[aä]g|gatan|gata|v[aä]gen|torget|plats)', normalize_swedish(line_lower)))
                # Also accept if it matches a known city
                norm_line = normalize_swedish(line_lower)
                is_known_city = any(city in norm_line for city in CITY_REGION_MAP)
                if is_addr or is_known_city:
                    event["location_raw"] = line.strip()
                    break
        # Pattern 4: Look for location in the broader page text near the event name
        if "location_raw" not in event:
            # FB sometimes shows: "<EventName>\n<Location>\n<Date>"
            name_raw = event.get("name_raw", "")
            if name_raw:
                name_idx = body_text.find(name_raw)
                if name_idx > 0:
                    after_name = body_text[name_idx + len(name_raw):name_idx + len(name_raw) + 300]
                    after_lines = [l.strip() for l in after_name.split('\n') if l.strip()]
                    for line in after_lines[:3]:
                        line_lower = line.lower()
                        norm_line = normalize_swedish(line_lower)
                        is_known_city = any(city in norm_line for city in CITY_REGION_MAP)
                        has_addr_indicator = bool(re.search(
                            r'(väg|gatan|gata|vägen|torget|plats|stigen|allé)',
                            line_lower))
                        if is_known_city or has_addr_indicator:
                            event["location_raw"] = line.strip()
                            break

        # Parse description: text after "Anyone on or off Facebook" or after address
        desc_lines = []
        found_start = False
        for line in lines:
            if 'Anyone on or off Facebook' in line:
                found_start = True
                continue
            if found_start:
                # Stop markers
                if line.startswith('Meet your host') or line.startswith('Suggested events'):
                    break
                # Stop at standalone city/location names (single word, capitalized)
                if re.match(r'^[A-ZÅÄÖ][a-zåäö]+(?:-[A-ZÅÄÖ][a-zåäö]+)?$', line) and len(line) < 30:
                    break
                # Skip "See more" / "See less" buttons that appear as text
                if line.strip() in ('See more', 'See less', 'Se mer', 'Se mindre'):
                    continue
                desc_lines.append(line)

        if desc_lines:
            # Clean "See more"/"See less" that might be inline at end of a line
            cleaned = []
            for line in desc_lines:
                line = re.sub(r'\s*See more\s*$', '', line)
                line = re.sub(r'\s*See less\s*$', '', line)
                line = re.sub(r'\s*Se mer\s*$', '', line)
                line = re.sub(r'\s*Se mindre\s*$', '', line)
                if line.strip():
                    cleaned.append(line)
            event["description_full"] = '\n'.join(cleaned)

    # 3. Parse date from page text
    # Facebook shows dates in several formats depending on how far away the event is
    header_area = body_text[:1500]

    # Strategy: find the main event area (after categories, around the title)
    # Look for the block: <day_number>\n<day_name> at <time>\n<event title>\n<address>
    event_name = event.get("name_raw", "")

    # Pattern A: Full date "Saturday, March 21, 2026 at 11 AM"
    full_date_pat = r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})\s+at\s+(\d{1,2}(?::\d{2})?)\s*(AM|PM)'
    # Search near the event title in the main area (second occurrence, after sidebar)
    main_area_idx = header_area.rfind(event_name)
    if main_area_idx < 0:
        main_area_idx = header_area.find(event_name)
    search_area = header_area[max(0, main_area_idx - 300):main_area_idx + 200] if main_area_idx > 0 else header_area

    date_match = re.search(full_date_pat, search_area)
    if date_match:
        month_str, day, year, time_str, ampm = date_match.groups()
        month = EN_MONTHS.get(month_str.lower(), 0)
        if month:
            event["date"] = f"{year}-{month:02d}-{int(day):02d}"

    # Pattern B: Relative "Saturday at 11 AM" with day number on previous line
    if "date" not in event:
        # Look for: \n<number>\n<Dayname> at <time>\n<event title>
        day_rel_pat = r'(\d{1,2})\n(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)(?:,?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4}))?\s+at\s+\d'
        rel_match = re.search(day_rel_pat, search_area)
        if rel_match:
            day_num = int(rel_match.group(1))
            # If we got month/year from a fuller format
            if rel_match.group(2):
                month = EN_MONTHS.get(rel_match.group(2).lower(), 0)
                year = int(rel_match.group(4)) if rel_match.group(4) else datetime.now().year
                if month:
                    event["date"] = f"{year}-{month:02d}-{day_num:02d}"
            else:
                # Pure relative date - guess from current date
                now = datetime.now()
                for month_offset in range(0, 6):
                    test_month = now.month + month_offset
                    test_year = now.year
                    while test_month > 12:
                        test_month -= 12
                        test_year += 1
                    try:
                        test_date = datetime(test_year, test_month, day_num)
                        if test_date >= now - timedelta(days=7):
                            event["date"] = test_date.strftime("%Y-%m-%d")
                            break
                    except ValueError:
                        continue

    # Pattern C: Date range "Sat, Apr 18 - Apr 19" or "Apr 18 - 19"
    if "date" not in event:
        range_patterns = [
            # "Sat, Apr 18 - Apr 19" or "Apr 18 - Apr 19"
            r'(\w{3,9})\s+(\d{1,2})\s*[-–]\s*(?:(\w{3,9})\s+)?(\d{1,2})(?:,?\s+(\d{4}))?',
        ]
        for pat in range_patterns:
            range_match = re.search(pat, search_area)
            if range_match:
                groups = range_match.groups()
                m1_str = groups[0]
                d1 = int(groups[1])
                m2_str = groups[2]
                d2 = int(groups[3])
                year = int(groups[4]) if groups[4] else datetime.now().year

                month1 = EN_MONTHS.get(m1_str.lower()[:3] if len(m1_str) > 3 else m1_str.lower(), 0)
                # Try 3-letter abbreviation
                if not month1:
                    for mname, mnum in EN_MONTHS.items():
                        if mname.startswith(m1_str.lower()):
                            month1 = mnum
                            break
                if month1:
                    event["date"] = f"{year}-{month1:02d}-{d1:02d}"
                    month2 = month1
                    if m2_str:
                        for mname, mnum in EN_MONTHS.items():
                            if mname.startswith(m2_str.lower()):
                                month2 = mnum
                                break
                    event["dateEnd"] = f"{year}-{month2:02d}-{d2:02d}"
                    break

    # Pattern D: "Saturday, June 6, 2026 at 2 PM" format in Details section
    if "date" not in event and details_idx > -1:
        details_area = body_text[max(0, details_idx - 500):details_idx]
        date_match = re.search(full_date_pat, details_area)
        if date_match:
            month_str, day, year, time_str, ampm = date_match.groups()
            month = EN_MONTHS.get(month_str.lower(), 0)
            if month:
                event["date"] = f"{year}-{month:02d}-{int(day):02d}"

    # 4. Try to extract location from description as last resort
    if "location_raw" not in event and event.get("description_full"):
        desc_text = event["description_full"]
        # Check if any known city appears in the description
        desc_norm = normalize_swedish(desc_text.lower())
        for city, region in CITY_REGION_MAP.items():
            if city in desc_norm:
                event["location_from_desc"] = city.title()
                break

    # Set dateEnd = date if not set
    if "date" in event and "dateEnd" not in event:
        event["dateEnd"] = event["date"]

    # Fallback: if still no date, mark it for manual entry
    if "date" not in event:
        event["date"] = "MANUAL_ENTRY_NEEDED"
        event["dateEnd"] = "MANUAL_ENTRY_NEEDED"
        print("  [!] Could not parse date - manual entry needed")

    return event


def clean_event_title(title):
    """Clean event title according to MC Kalendern rules.
    - Remove city/location from title
    - Remove country in parentheses
    - Remove emoji
    """
    # Remove emoji
    title = re.sub(r'[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F\U0000200D]', '', title)
    # Remove country in parentheses
    title = re.sub(r'\s*\(Sverige\)\s*', ' ', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(Sweden\)\s*', ' ', title, flags=re.IGNORECASE)
    # Clean up whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title


# =============================================================================
# Location and Region
# =============================================================================

def normalize_swedish(text):
    """Remove Swedish special chars for matching."""
    return (text.lower()
            .replace('å', 'a').replace('ä', 'a').replace('ö', 'o')
            .replace('é', 'e').replace('ü', 'u'))


def guess_region(location_str):
    """Guess SMC region from location string."""
    loc_norm = normalize_swedish(location_str.lower())

    for city, region in CITY_REGION_MAP.items():
        if city in loc_norm:
            return region

    return None


def clean_location(location_raw):
    """Clean location to short format for card display (under 80 chars).
    Input: 'Karins väg 5, 19461 Upplands-Väsby, Sweden'
    Output: 'Karins väg 5, Upplands Väsby'
    """
    loc = location_raw
    # Remove country
    loc = re.sub(r',?\s*(Sweden|Sverige)\s*$', '', loc, flags=re.IGNORECASE)
    # Remove postal code
    loc = re.sub(r',?\s*\d{3}\s?\d{2}\s*', ', ', loc)
    # Clean double commas and whitespace
    loc = re.sub(r',\s*,', ',', loc)
    loc = re.sub(r'\s+', ' ', loc).strip().strip(',').strip()

    # Truncate if over 80 chars
    if len(loc) > 80:
        loc = loc[:77] + "..."
    return loc


# =============================================================================
# Event Type Guessing
# =============================================================================

def guess_event_type(name, description=""):
    """Guess event type from name and description."""
    text = normalize_swedish(f"{name} {description}".lower())

    scores = {}
    for etype, keywords in TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[etype] = score

    if not scores:
        return "Träff"  # Default

    # Map internal names to display names
    type_map = {
        "Traff": "Träff",
        "Korning": "Körning",
        "Show": "Show",
        "Fest": "Fest",
        "Racing": "Racing",
    }

    best = max(scores, key=scores.get)
    return type_map.get(best, "Träff")


# =============================================================================
# Description Generation
# =============================================================================

def make_short_description(full_desc, max_len=180):
    """Create a front-card description from full text.

    Target: max ~4 lines on the card = roughly 150-180 chars.
    Strategy:
    1. Take complete sentences that fit within max_len
    2. If first sentence alone is too long, cut at last word boundary
    3. Remove filler phrases like "Varmt valkomna" if they push over limit
    """
    if not full_desc:
        return ""

    # Flatten to single line for processing, then split into sentences
    text = full_desc.replace('\n', ' ').strip()
    # Remove "See more"/"See less" remnants
    text = re.sub(r'\s*(See more|See less|Se mer|Se mindre)\s*', '', text)

    # Split on sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)

    # Build up from complete sentences
    short = ""
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        candidate = (short + " " + s).strip() if short else s
        if len(candidate) <= max_len:
            short = candidate
        else:
            break

    short = short.strip()

    # If nothing fit (first sentence > max_len), truncate at word boundary
    if not short and sentences:
        first = sentences[0]
        if len(first) > max_len:
            # Cut at last space before max_len
            cut_pos = first[:max_len - 3].rfind(' ')
            if cut_pos > 50:
                short = first[:cut_pos] + "..."
            else:
                short = first[:max_len - 3] + "..."
        else:
            short = first

    # If still too short (< 80 chars), try adding more text
    if len(short) < 80 and len(sentences) > 1:
        remaining = ' '.join(sentences[1:])
        space_left = max_len - len(short) - 1
        if space_left > 20:
            # Add as much as fits at word boundary
            chunk = remaining[:space_left]
            cut_pos = chunk.rfind(' ')
            if cut_pos > 10:
                short = short + " " + chunk[:cut_pos] + "..."

    # Final safety: hard truncate if somehow over
    if len(short) > max_len:
        cut_pos = short[:max_len - 3].rfind(' ')
        short = short[:cut_pos] + "..." if cut_pos > 50 else short[:max_len - 3] + "..."

    return short


# =============================================================================
# ID Generation
# =============================================================================

def make_event_id(name, location, date):
    """Generate event ID from name, location, date."""
    # Normalize
    text = normalize_swedish(f"{name} {location}")
    # Keep only alphanumeric and spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Convert to kebab-case
    parts = text.split()[:5]  # Max 5 words
    slug = '-'.join(parts)

    # Add year
    year = date[:4] if date else str(datetime.now().year)

    return f"{slug}-{year}"


# =============================================================================
# Google Maps Link
# =============================================================================

def make_maps_link(location):
    """Create Google Maps search link from location string."""
    from urllib.parse import quote_plus
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(location)}"


# =============================================================================
# Dedup Against events.js
# =============================================================================

def load_events_js(path):
    """Load and parse events.js file."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract JSON from the JS file
    start = content.index('{')
    end = content.rindex('}') + 1
    json_str = content[start:end]
    data = json.loads(json_str)
    return data.get('events', [])


def normalize_for_dedup(text):
    """Normalize text for dedup comparison."""
    text = normalize_swedish(text.lower())
    text = re.sub(r'[^a-z0-9\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def find_duplicates(new_event, existing_events, threshold=0.5):
    """Check if event already exists in the calendar.
    Uses two strategies:
    1. Same date + name word overlap >= threshold
    2. Very high name similarity regardless of date (catches renamed/moved events)
    """
    new_name = normalize_for_dedup(new_event.get("name", ""))
    new_date = new_event.get("date", "")
    new_words = set(new_name.split())

    matches = []
    for evt in existing_events:
        if evt.get("_canary") or evt.get("_ad"):
            continue

        existing_name = normalize_for_dedup(evt.get("name", ""))
        existing_date = evt.get("date", "")
        existing_words = set(existing_name.split())

        if not new_words or not existing_words:
            continue

        # Word overlap similarity
        overlap = len(new_words & existing_words)
        union = len(new_words | existing_words)
        similarity = overlap / union if union > 0 else 0

        # Also check if one name contains the other
        containment = 0
        if new_name in existing_name or existing_name in new_name:
            containment = min(len(new_name), len(existing_name)) / max(len(new_name), len(existing_name))

        best_score = max(similarity, containment)

        # Match conditions:
        # 1. Same date + reasonable name match
        # 2. Very high name match (>0.8) even with different dates
        is_match = False
        if new_date and existing_date and new_date == existing_date and best_score >= threshold:
            is_match = True
        elif best_score >= 0.8:
            is_match = True

        if is_match:
            matches.append({
                "existing_id": evt["id"],
                "existing_name": evt["name"],
                "existing_date": evt.get("date"),
                "similarity": round(best_score, 2),
            })

    # Sort by similarity descending
    matches.sort(key=lambda x: x["similarity"], reverse=True)
    return matches[:5]  # Max 5 matches


# =============================================================================
# Image Download
# =============================================================================

def process_back_image(source_path, event_id, date):
    """Process a local image file: resize to 800px wide, save to ads/ folder.

    Args:
        source_path: Path to the source image (can be ugly FB filename)
        event_id: Event ID for naming
        date: Event date for naming

    Returns:
        Relative path like 'ads/event-name-back-2026-05-16.jpg' or None
    """
    import subprocess
    import shutil

    source = Path(source_path)

    # If path is relative, try resolving from project root (parent of tools/)
    if not source.is_absolute():
        # Try relative to project root
        project_root = SCRIPT_DIR.parent
        source = project_root / source_path
        if not source.exists():
            # Try relative to current dir
            source = Path(source_path)

    if not source.exists():
        print(f"  [!] Image file not found: {source_path}")
        return None

    # Target filename
    target_name = f"{event_id}-back-{date}.jpg"
    target_path = DEFAULT_ADS_DIR / target_name
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Try to resize with ImageMagick (convert/magick)
    resized = False
    for cmd_name in ['magick', 'convert']:
        try:
            result = subprocess.run(
                [cmd_name, str(source), '-resize', '800x', '-quality', '85', str(target_path)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                resized = True
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue

    # Fallback: try PIL/Pillow
    if not resized:
        try:
            from PIL import Image
            img = Image.open(source)
            # Resize to 800px wide, keep aspect ratio
            w, h = img.size
            new_w = 800
            new_h = int(h * (new_w / w))
            img = img.resize((new_w, new_h), Image.LANCZOS)
            img.save(target_path, 'JPEG', quality=85)
            resized = True
        except ImportError:
            pass
        except Exception as e:
            print(f"  [!] PIL resize failed: {e}")

    # Last fallback: just copy the file
    if not resized:
        shutil.copy2(source, target_path)
        print(f"  [i] Could not resize (no ImageMagick or PIL). Copied original.")

    # Show result
    try:
        size_kb = target_path.stat().st_size / 1024
        print(f"  Image: {source.name} -> ads/{target_name} ({size_kb:.0f} KB)")
    except Exception:
        print(f"  Image: ads/{target_name}")

    return f"ads/{target_name}"


def download_cover_image(url, event_id, date, driver=None):
    """Download the cover image from a Facebook event page."""
    if not driver:
        print("  [!] Cannot download image without browser")
        return None

    try:
        # Find the largest image on the page (likely the cover)
        images = driver.execute_script("""
            return Array.from(document.querySelectorAll('img'))
                .filter(i => i.naturalWidth > 400)
                .map(i => ({src: i.src, w: i.naturalWidth, h: i.naturalHeight}))
                .sort((a, b) => (b.w * b.h) - (a.w * a.h));
        """)

        if not images:
            print("  [!] No suitable cover image found")
            return None

        img_url = images[0]['src']
        print(f"  Downloading cover image ({images[0]['w']}x{images[0]['h']})...")

        # Download via requests (using the browser's cookies)
        cookies = {c['name']: c['value'] for c in driver.get_cookies()}
        headers = {'User-Agent': driver.execute_script("return navigator.userAgent")}

        resp = requests.get(img_url, cookies=cookies, headers=headers, timeout=15)
        if resp.status_code == 200:
            # Save to ads/ folder
            filename = f"{event_id}-back-{date}.jpg"
            filepath = DEFAULT_ADS_DIR / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'wb') as f:
                f.write(resp.content)

            print(f"  Saved: ads/{filename}")
            return f"ads/{filename}"
    except Exception as e:
        print(f"  [!] Image download failed: {e}")

    return None


# =============================================================================
# Output Formatting
# =============================================================================

def format_event_json(event):
    """Format extracted event data as a ready-to-paste events.js entry."""
    name = event.get("name", "Unknown Event")
    date = event.get("date", "2026-01-01")
    date_end = event.get("dateEnd", date)

    # Location: prefer location_raw, fall back to location_from_desc
    location_raw = event.get("location_raw", "")
    if location_raw:
        location = clean_location(location_raw)
    elif event.get("location_from_desc"):
        location = event["location_from_desc"]
        print(f"  [i] Location guessed from description: {location}")
    else:
        location = ""
        print("  [!] No location found - manual entry needed")

    organizer = event.get("organizer", "")
    desc_full = event.get("description_full", "")
    desc_short = make_short_description(desc_full)
    event_type = guess_event_type(name, desc_full)
    region = guess_region(location_raw or location)
    event_id = make_event_id(name, location, date)
    url = event.get("url", "")
    back_image = event.get("back_image")

    entry = {
        "id": event_id,
        "name": name,
        "date": date,
        "dateEnd": date_end,
        "location": location,
        "type": event_type,
        "organizer": organizer,
        "description": desc_short,
    }

    if back_image:
        entry["backImage"] = back_image

    # Build links
    links = []
    links.append({"label": "Facebook", "url": url})

    # Add organizer website if we can guess it
    if organizer:
        org_slug = normalize_swedish(organizer.lower()).replace(' ', '')
        # Could add website lookup here in the future

    maps_query = event.get("location_raw", location)
    links.append({
        "label": "Karta",
        "url": make_maps_link(maps_query),
        "type": "map"
    })

    entry["links"] = links
    entry["link"] = url
    entry["region"] = region or "Stockholm"
    entry["source"] = "facebook.com"

    if desc_full:
        # Format descriptionFull with proper line breaks
        paragraphs = [p.strip() for p in desc_full.split('\n') if p.strip()]
        entry["descriptionFull"] = '\n\n'.join(paragraphs)

    return entry


def print_event_card(event_json, duplicates=None):
    """Pretty-print an event card for review."""
    print("\n" + "=" * 60)
    print(f"  Name:      {event_json['name']}")
    print(f"  Date:      {event_json['date']}", end="")
    if event_json.get('dateEnd') != event_json.get('date'):
        print(f" to {event_json['dateEnd']}", end="")
    print()
    print(f"  Location:  {event_json['location']}")
    print(f"  Type:      {event_json['type']}")
    print(f"  Organizer: {event_json.get('organizer', 'N/A')}")
    print(f"  Region:    {event_json['region']}")
    print(f"  ID:        {event_json['id']}")

    if event_json.get('description'):
        desc = event_json['description']
        if len(desc) > 100:
            desc = desc[:97] + "..."
        print(f"  Desc:      {desc}")

    if event_json.get('backImage'):
        print(f"  Image:     {event_json['backImage']}")

    if duplicates:
        print(f"\n  [!] POSSIBLE DUPLICATES:")
        for d in duplicates:
            print(f"      - {d['existing_name']} ({d['existing_date']}) "
                  f"[similarity: {d['similarity']}]")

    print("=" * 60)


# =============================================================================
# Validation
# =============================================================================

def validate_event(event_json):
    """Validate event data before adding to events.js.
    Returns (is_valid, warnings, errors).
    Errors block adding, warnings are shown but don't block.
    """
    warnings = []
    errors = []

    # 1. Type must be valid Swedish
    etype = event_json.get('type', '')
    if etype not in VALID_TYPES:
        # Try to auto-fix common issues
        type_fixes = {
            'Traff': 'Träff', 'traff': 'Träff',
            'Korning': 'Körning', 'korning': 'Körning',
            'show': 'Show', 'fest': 'Fest', 'racing': 'Racing',
        }
        if etype in type_fixes:
            fixed = type_fixes[etype]
            event_json['type'] = fixed
            warnings.append(f"Type auto-fixed: '{etype}' -> '{fixed}'")
        else:
            errors.append(f"Invalid type: '{etype}'. Must be one of: {', '.join(sorted(VALID_TYPES))}")

    # 2. Region must be valid
    region = event_json.get('region', '')
    if region not in VALID_REGIONS:
        errors.append(f"Invalid region: '{region}'. Must be one of the 21 SMC regions.")

    # 3. Region should not default to Stockholm without evidence
    if region == 'Stockholm':
        location = event_json.get('location', '')
        loc_norm = normalize_swedish(location.lower())
        stockholm_cities = [c for c, r in CITY_REGION_MAP.items() if r == 'Stockholm']
        is_stockholm = any(city in loc_norm for city in stockholm_cities)
        if not is_stockholm and location:
            warnings.append(f"Region is 'Stockholm' but location '{location}' doesn't match any Stockholm city. Please verify.")

    # 4. Date must be valid
    date = event_json.get('date', '')
    if date == 'MANUAL_ENTRY_NEEDED' or not date:
        errors.append("Date is missing or could not be parsed.")
    else:
        try:
            datetime.strptime(date, '%Y-%m-%d')
        except ValueError:
            errors.append(f"Invalid date format: '{date}'. Expected YYYY-MM-DD.")

    # 5. Name should not be empty
    if not event_json.get('name', '').strip():
        errors.append("Event name is empty.")

    # 6. Description should be 80-200 chars
    desc = event_json.get('description', '')
    if len(desc) < 30:
        warnings.append(f"Description is very short ({len(desc)} chars). Consider adding more detail.")
    elif len(desc) > 200:
        warnings.append(f"Description is long ({len(desc)} chars). Front card shows max ~4 lines.")

    # 7. Location should not be empty
    if not event_json.get('location', '').strip():
        warnings.append("Location is empty. Event will show without address on the card.")

    # 8. backImage should be set for Type 1 cards
    if not event_json.get('backImage'):
        warnings.append("No backImage set. Card will not have a flip side image.")

    return len(errors) == 0, warnings, errors


def print_validation_result(is_valid, warnings, errors):
    """Print validation results in a clear format."""
    if errors:
        print("\n  VALIDATION ERRORS (must fix before adding):")
        for e in errors:
            print(f"    [X] {e}")
    if warnings:
        print("\n  WARNINGS (review before confirming):")
        for w in warnings:
            print(f"    [!] {w}")
    if is_valid and not warnings:
        print("\n  Validation: all checks passed")


# =============================================================================
# Add Event to events.js
# =============================================================================

def add_event_to_events_js(event_json, events_js_path):
    """Insert a new event into events.js in the correct date-sorted position.

    The file format is:
      /* copyright header */
      const EVENTS_DATA = { "lastUpdated": "...", "events": [ ... ] };

    We parse the JSON, insert the event, and write back.
    """
    path = Path(events_js_path)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract the header (everything before the JSON starts)
    json_start = content.index('{')
    header = content[:json_start]
    # The prefix before the JSON (e.g. "const EVENTS_DATA = ")
    prefix_line = header.split('\n')[-1] if '\n' in header else header
    header_comments = header[:header.rfind('\n') + 1] if '\n' in header else ''

    # Extract JSON
    json_end = content.rindex('}') + 1
    suffix = content[json_end:]  # Usually just ";\n"
    json_str = content[json_start:json_end]

    data = json.loads(json_str)
    events = data.get('events', [])

    # Check if event ID already exists
    existing_ids = {e['id'] for e in events}
    if event_json['id'] in existing_ids:
        print(f"  [!] Event ID '{event_json['id']}' already exists in events.js")
        print(f"      Use a different ID or remove the existing one first.")
        return False

    # Find correct insertion position (after ADs, sorted by date)
    # ADs are always at the beginning, then events sorted by date
    ad_end_idx = 0
    for i, e in enumerate(events):
        if e.get('_ad'):
            ad_end_idx = i + 1
        else:
            break

    # Find position among real events (sorted by date ascending)
    new_date = event_json.get('date', '9999-99-99')
    insert_idx = ad_end_idx
    for i in range(ad_end_idx, len(events)):
        evt_date = events[i].get('date', '')
        if evt_date > new_date:
            insert_idx = i
            break
    else:
        insert_idx = len(events)

    # Insert
    events.insert(insert_idx, event_json)

    # Update lastUpdated
    data['lastUpdated'] = datetime.now(tz=__import__('datetime').timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data['events'] = events

    # Write back
    json_output = json.dumps(data, indent=2, ensure_ascii=False)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(header_comments + prefix_line + json_output + suffix)

    total = len(events)
    real = sum(1 for e in events if not e.get('_canary') and not e.get('_ad'))
    canaries = sum(1 for e in events if e.get('_canary'))
    ads = sum(1 for e in events if e.get('_ad'))

    print(f"\n  Added to events.js at position {insert_idx}")
    print(f"  Total: {total} events ({real} real + {canaries} canaries + {ads} ads)")

    # Verify canary count
    if canaries != 6:
        print(f"  [!!!] WARNING: Expected 6 canaries, found {canaries}!")

    return True


# =============================================================================
# Main Commands
# =============================================================================

def cmd_extract(urls, args):
    """Extract event data from one or more Facebook event URLs."""
    driver = None
    results = []

    if not args.no_browser:
        print("Starting Chrome browser...")
        driver = create_driver(headless=args.headless)
        if not driver:
            print("[!] Chrome not available. Install with:")
            print("    pip install undetected-chromedriver selenium")
            print("    Falling back to limited extraction.")

    # Load existing events for dedup
    existing_events = []
    events_js_path = Path(args.events_js)
    if events_js_path.exists():
        print(f"Loading events from {events_js_path}...")
        existing_events = load_events_js(events_js_path)
        print(f"  Loaded {len(existing_events)} existing events")

    for url in urls:
        print(f"\nProcessing: {url}")

        # Validate URL
        if 'facebook.com/events/' not in url:
            print(f"  [!] Not a Facebook event URL, skipping")
            continue

        try:
            if driver:
                event = extract_with_browser(url, driver)
            else:
                print("  [!] No browser available, skipping")
                continue

            # Format as events.js entry
            event_json = format_event_json(event)

            # Download image if requested
            if args.download_images and driver:
                img_path = download_cover_image(url, event_json['id'],
                                                event_json['date'], driver)
                if img_path:
                    event_json['backImage'] = img_path

            # Add back image if provided via CLI
            if args.back_image:
                source_path = args.back_image
                # Check if it looks like it's already in ads/ with correct naming
                if (source_path.startswith('ads/') and
                    event_json['id'] in source_path):
                    # Already processed, just use it
                    event_json['backImage'] = source_path
                else:
                    # Process: resize to 800px, rename, copy to ads/
                    processed = process_back_image(
                        source_path, event_json['id'], event_json['date'])
                    if processed:
                        event_json['backImage'] = processed

            # Check for duplicates
            duplicates = find_duplicates(event_json, existing_events)

            # Display
            print_event_card(event_json, duplicates)

            # Add to events.js if --add flag is set
            added = False
            if args.add:
                if duplicates:
                    print(f"\n  [!] Skipping --add: event has {len(duplicates)} possible duplicate(s)")
                    print(f"      Use --force-add to add anyway (not implemented yet)")
                else:
                    # Validate before adding
                    is_valid, warnings, errors = validate_event(event_json)
                    print_validation_result(is_valid, warnings, errors)

                    if not is_valid:
                        print("\n  [X] Cannot add: fix the errors above first.")
                    else:
                        # Show what we are about to add and ask for confirmation
                        print("\n  Ready to add this event to events.js.")
                        print("  JSON preview:")
                        preview = json.dumps(event_json, indent=4, ensure_ascii=False)
                        for line in preview.split('\n'):
                            print(f"    {line}")

                        try:
                            answer = input("\n  Add this event? [y/N] ").strip().lower()
                            if answer in ('y', 'yes'):
                                added = add_event_to_events_js(event_json, args.events_js)
                            else:
                                print("  Skipped.")
                        except (EOFError, KeyboardInterrupt):
                            print("\n  Skipped.")

            results.append({
                "event": event_json,
                "duplicates": duplicates,
                "is_new": len(duplicates) == 0,
                "added": added,
            })

            # Be nice to Facebook
            time.sleep(3)

        except Exception as e:
            print(f"  [!] Error: {e}")
            import traceback
            traceback.print_exc()

    if driver:
        driver.quit()

    return results


def cmd_batch(filepath, args):
    """Process URLs from a file."""
    path = Path(filepath)
    if not path.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    urls = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and 'facebook.com' in line:
                urls.append(line)

    print(f"Found {len(urls)} URLs in {filepath}")
    return cmd_extract(urls, args)


def cmd_check_new(filepath, args):
    """Extract events and show only NEW ones (not in events.js)."""
    results = cmd_batch(filepath, args)

    new_events = [r for r in results if r['is_new']]
    dup_events = [r for r in results if not r['is_new']]

    print("\n" + "=" * 60)
    print(f"SUMMARY: {len(new_events)} new, {len(dup_events)} already in calendar")
    print("=" * 60)

    if new_events:
        print("\nNEW EVENTS (ready to add):")
        print("-" * 40)
        for r in new_events:
            e = r['event']
            print(f"  {e['date']}  {e['name']}  ({e['location']})")

        # Output JSON for new events
        print("\n\nJSON for events.js:")
        print("-" * 40)
        for r in new_events:
            print(json.dumps(r['event'], indent=2, ensure_ascii=False))
            print(",")

    if dup_events:
        print("\nALREADY IN CALENDAR:")
        print("-" * 40)
        for r in dup_events:
            e = r['event']
            d = r['duplicates'][0]
            print(f"  {e['name']} -> matches '{d['existing_name']}' "
                  f"(similarity: {d['similarity']})")

    return results


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="FB Event Tool for MC Kalendern",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Extract command
    extract_parser = subparsers.add_parser("extract", help="Extract event(s) from URL(s)")
    extract_parser.add_argument("urls", nargs="+", help="Facebook event URL(s)")

    # Batch command
    batch_parser = subparsers.add_parser("batch", help="Process URLs from a file")
    batch_parser.add_argument("file", help="Text file with URLs (one per line)")

    # Check-new command
    check_parser = subparsers.add_parser("check-new", help="Find new events not in calendar")
    check_parser.add_argument("file", help="Text file with URLs (one per line)")

    # Common options
    for p in [extract_parser, batch_parser, check_parser]:
        p.add_argument("--no-browser", action="store_true",
                       help="Skip Selenium, use requests only")
        p.add_argument("--download-images", action="store_true",
                       help="Download cover images to ads/")
        p.add_argument("--events-js", default=str(DEFAULT_EVENTS_JS),
                       help="Path to events.js")
        p.add_argument("--output", help="Write JSON output to file")
        p.add_argument("--headless", action="store_true", default=False,
                       help="Run Chrome in headless mode")
        p.add_argument("--add", action="store_true", default=False,
                       help="Add new events directly to events.js (Type 1 card)")
        p.add_argument("--back-image", default=None,
                       help="Path to back image (any FB filename OK - auto resizes to 800px, renames, copies to ads/)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "extract":
        results = cmd_extract(args.urls, args)
    elif args.command == "batch":
        results = cmd_batch(args.file, args)
    elif args.command == "check-new":
        results = cmd_check_new(args.file, args)
    else:
        parser.print_help()
        sys.exit(1)

    # Write output if requested
    if args.output and results:
        output_data = [r['event'] for r in results if r.get('is_new', True)]
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"\nOutput written to: {args.output}")


if __name__ == "__main__":
    main()
