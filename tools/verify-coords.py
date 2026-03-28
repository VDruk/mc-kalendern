#!/usr/bin/env python3
"""
Verify LOCATION_COORDS in index.html against Nominatim (OpenStreetMap) geocoding.
Flags entries where our coordinates are more than 15 km from what OSM says.

Usage:
  python tools/verify-coords.py                  # check all entries
  python tools/verify-coords.py fotskäl sala     # check specific entries
  python tools/verify-coords.py --new            # check entries added in last git commit
"""

import re, sys, json, time, math, subprocess

INDEX_FILE = "index.html"
THRESHOLD_KM = 15  # flag if distance exceeds this

def haversine(lat1, lon1, lat2, lon2):
    """Distance in km between two lat/lon points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def extract_coords(filepath):
    """Extract all LOCATION_COORDS entries from index.html."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the LOCATION_COORDS block
    pattern = r"'([^']+)'\s*:\s*\{\s*lat\s*:\s*([\d.-]+)\s*,\s*lon\s*:\s*([\d.-]+)\s*\}"
    matches = re.findall(pattern, content)

    coords = {}
    for name, lat, lon in matches:
        coords[name] = (float(lat), float(lon))
    return coords

def geocode_nominatim(place_name):
    """Look up a place name via Nominatim. Returns (lat, lon) or None."""
    import urllib.request, urllib.parse
    # Add Sweden bias for better results
    query = f"{place_name}, Sweden"
    params = urllib.parse.urlencode({
        'q': query,
        'format': 'json',
        'limit': 1,
        'countrycodes': 'se,dk,no,fi,es,cz,at'
    })
    url = f"https://nominatim.openstreetmap.org/search?{params}"
    req = urllib.request.Request(url, headers={'User-Agent': 'MCKalendern-CoordCheck/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception as e:
        print(f"  [!] Geocoding failed for '{place_name}': {e}")
    return None

def get_new_entries():
    """Get LOCATION_COORDS entries added in the last commit."""
    try:
        diff = subprocess.check_output(
            ['git', 'diff', 'HEAD~1', '--', INDEX_FILE],
            text=True, stderr=subprocess.DEVNULL
        )
        # Find added lines with coords
        pattern = r"'([^']+)'\s*:\s*\{\s*lat\s*:\s*[\d.-]+\s*,\s*lon\s*:\s*[\d.-]+\s*\}"
        new_names = []
        for line in diff.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                for match in re.finditer(pattern, line):
                    new_names.append(match.group(1))
        return new_names
    except Exception:
        print("Could not get git diff. Checking all entries instead.")
        return None

def main():
    coords = extract_coords(INDEX_FILE)
    print(f"Found {len(coords)} LOCATION_COORDS entries.\n")

    # Determine which entries to check
    if len(sys.argv) > 1:
        if sys.argv[1] == '--new':
            names = get_new_entries()
            if names is None or len(names) == 0:
                print("No new entries found in last commit.")
                return
            print(f"Checking {len(names)} new entries from last commit.\n")
        else:
            names = sys.argv[1:]
            print(f"Checking {len(names)} specified entries.\n")
    else:
        # Skip region fallbacks and country fallbacks
        skip = {'västernorrland', 'västra götaland', 'dalarna', 'jämtland', 'norrbotten',
                'gävleborg', 'halland', 'kronoberg', 'blekinge', 'gotland', 'skåne',
                'stockholm', 'södermanland', 'uppsala', 'värmland', 'västerbotten',
                'västmanland', 'örebro', 'östergötland', 'jönköping', 'kalmar',
                'spanien', 'danmark', 'norge', 'finland', 'österrike',
                'dalsland', 'vättern', 'vänern', 'mälardalen', 'vidöstern', 'åland',
                'bornholm', 'gotland ring', 'sverige'}
        names = [n for n in coords.keys() if n not in skip]
        print(f"Checking {len(names)} city entries (skipping region fallbacks).\n")

    issues = []
    checked = 0

    for name in names:
        if name not in coords:
            print(f"  [?] '{name}' not found in LOCATION_COORDS")
            continue

        our_lat, our_lon = coords[name]
        result = geocode_nominatim(name)

        if result is None:
            print(f"  [?] '{name}' - could not geocode (may be too specific or foreign)")
            time.sleep(1.1)
            continue

        osm_lat, osm_lon = result
        dist = haversine(our_lat, our_lon, osm_lat, osm_lon)

        if dist > THRESHOLD_KM:
            status = "MISMATCH"
            issues.append((name, dist, our_lat, our_lon, osm_lat, osm_lon))
            print(f"  [X] '{name}': {dist:.1f} km off! Ours: ({our_lat}, {our_lon}) vs OSM: ({osm_lat:.4f}, {osm_lon:.4f})")
        else:
            print(f"  [OK] '{name}': {dist:.1f} km")

        checked += 1
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec

    print(f"\n{'='*60}")
    print(f"Checked: {checked} | Issues: {len(issues)} (>{THRESHOLD_KM} km off)")
    if issues:
        print(f"\nEntries to fix:")
        for name, dist, our_lat, our_lon, osm_lat, osm_lon in issues:
            print(f"  '{name}': currently ({our_lat}, {our_lon}), should be ~({osm_lat:.2f}, {osm_lon:.2f}) [{dist:.1f} km off]")
    else:
        print("All checked entries look good!")

if __name__ == "__main__":
    main()
