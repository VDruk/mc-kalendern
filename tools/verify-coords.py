#!/usr/bin/env python3
"""
Verify LOCATION_COORDS in index.html by generating Google Maps links.
Open each link to visually confirm the dot is in the right place.

Usage:
  python tools/verify-coords.py                  # list all with Google Maps links
  python tools/verify-coords.py jättendal         # check one city
  python tools/verify-coords.py --diff            # check only coords changed in last commit
  python tools/verify-coords.py --compare CITY    # show our coords vs Google Maps search side by side

Output: For each entry, prints a Google Maps link centered on OUR coordinates.
If the pin is NOT on the city/town, the coords are wrong.
"""

import re, sys, subprocess

def load_coords(filepath='index.html'):
    """Extract LOCATION_COORDS from index.html."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    coords = {}
    pattern = r"'([^']+)'\s*:\s*\{\s*lat:\s*([\d.-]+)\s*,\s*lon:\s*([\d.-]+)\s*\}"
    for m in re.finditer(pattern, content):
        name, lat, lon = m.group(1), float(m.group(2)), float(m.group(3))
        coords[name] = (lat, lon)
    return coords

# Region/country fallbacks - not real cities, skip
SKIP = {'sverige', 'spanien', 'danmark', 'norge', 'finland', 'tjeckien', 'österrike',
        'dalsland', 'vättern', 'vänern', 'mälardalen', 'vidöstern', 'åland', 'bornholm',
        'västra götaland', 'östergötland', 'södermanland', 'gotland ring'}

def main():
    single_city = None
    diff_mode = False
    
    for arg in sys.argv[1:]:
        if arg == '--diff':
            diff_mode = True
        elif not arg.startswith('--'):
            single_city = arg.lower()
    
    coords = load_coords()
    print(f"Loaded {len(coords)} LOCATION_COORDS entries\n")
    
    if single_city:
        check = {k: v for k, v in coords.items() if single_city in k}
    elif diff_mode:
        # Get changed lines from last commit
        try:
            diff = subprocess.check_output(['git', 'diff', 'HEAD~1', 'index.html'], text=True)
            changed = set()
            for line in diff.split('\n'):
                if line.startswith('+') and 'lat:' in line:
                    for m in re.finditer(r"'([^']+)'\s*:", line):
                        changed.add(m.group(1))
            check = {k: v for k, v in coords.items() if k in changed}
            print(f"Found {len(check)} changed coords in last commit\n")
        except:
            print("Could not get git diff. Checking all.")
            check = coords
    else:
        check = coords
    
    if not check:
        print(f"No matches found for '{single_city or 'diff'}'")
        return
    
    for name, (lat, lon) in sorted(check.items()):
        if name in SKIP:
            continue
        
        # Our pin location
        pin_url = f"https://www.google.com/maps?q={lat},{lon}&z=13"
        # What Google thinks the city is
        search_url = f"https://www.google.com/maps/search/{name}+Sweden"
        
        print(f"  {name}")
        print(f"    Ours:   lat {lat}, lon {lon}")
        print(f"    Pin:    {pin_url}")
        print(f"    Search: {search_url}")
        print()
    
    print("HOW TO VERIFY:")
    print("  1. Open the 'Pin' link - this shows where OUR dot will be")
    print("  2. Open the 'Search' link - this shows where Google thinks the city is")
    print("  3. If they don't match, update the coords in index.html")
    print()
    print("QUICK CHECK (single city):")
    print("  python tools/verify-coords.py jättendal")

if __name__ == '__main__':
    main()
