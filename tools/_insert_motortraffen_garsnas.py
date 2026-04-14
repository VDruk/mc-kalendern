#!/usr/bin/env python3
"""Insert 3 Motorträffen i Gärsnäs 2026 events (premiär, nationaldag, avslutning)."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/671681114_1363844085775744_9087745525400221918_n.jpg'
dst = 'ads/motortraffen-garsnas-back-2026.jpg'
im = Image.open(src)
if im.mode in ('RGBA', 'P'):
    im = im.convert('RGB')
if im.width != 800:
    new_h = int(round(im.height * 800 / im.width))
    im = im.resize((800, new_h), Image.LANCZOS)
im.save(dst, 'JPEG', quality=85, optimize=True)
print(f'Image saved: {im.size}')

with open('events.js', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'const\s+EVENTS_DATA\s*=\s*', content)
header = content[:m.end()]
data = json.loads(content[m.end():].rstrip().rstrip(';').rstrip())

fb_page = "https://www.facebook.com/111motor"
fb_post = "https://www.facebook.com/photo?fbid=1363844082442411&set=a.466300335530128"
location = "Stenhedsvägen 3, 272 61 Gärsnäs"
map_url = "https://www.google.com/maps/search/?api=1&query=Stenhedsv%C3%A4gen+3+G%C3%A4rsn%C3%A4s"
organizer = "Gärsnäs AIS"

series_note = (
    "Träffarna arrangeras av Gärsnäs AIS motorträffskommitté vid grillplatsen "
    "bredvid Österlenvulk AB i Gärsnäs. Bilar, motorcyklar, mopeder, traktorer m.m. "
    "Försäljning av korv, dricka och kaffe. Kontakt: Lars-Göran 070-5496999."
)

dates_info = (
    "Säsongens datum 2026:\n"
    "Tisdag 5 maj kl 18.00 (premiär, Sparbanken Syd bjuder på popcorn, tävling finaste moped, mc, amerikanare, europabil och epa-traktor)\n"
    "Tisdag 19 maj kl 18.00\n"
    "Tisdag 2 juni kl 18.00\n"
    "Lördag 6 juni kl 16.00 (OBS: dag och tid, Sveriges nationaldag)\n"
    "Tisdag 7 juli kl 18.00\n"
    "Tisdag 21 juli kl 18.00 (musikuppträde, CC and the young ones)\n"
    "Tisdag 4 augusti kl 18.00\n"
    "Tisdag 18 augusti kl 18.00 (musikuppträde, Josefin Nilsson, Veberöd)\n"
    "Tisdag 1 september kl 18.00\n"
    "Söndag 13 september kl 12.00 (avslutning, tipsrunda start mellan 12.30-13.30)"
)

events_to_add = [
    {
        "id": "motortraffen-garsnas-premiar-2026-05-05",
        "name": "Motorträffen - Premiär",
        "date": "2026-05-05",
        "dateEnd": "2026-05-05",
        "type": "Träff",
        "region": "Skåne",
        "location": location,
        "organizer": organizer,
        "description": (
            "Säsongspremiär för motorträffen i Gärsnäs. Start kl 18. Sparbanken Syd bjuder på popcorn. "
            "Tävling om finaste moped, mc, amerikanare, europabil och epa-traktor."
        ),
        "descriptionFull": (
            "Säsongspremiär för motorträffen vid grillplatsen bredvid Österlenvulk AB i Gärsnäs. "
            "Start kl 18.00.\n\n"
            "Sparbanken Syd bjuder på popcorn till alla barn. De utser också finaste moped, "
            "motorcykel, amerikanare, europabil och epa-traktor.\n\n"
            + series_note + "\n\n" + dates_info
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": fb_post,
        "links": [
            {"label": "FB Sida", "url": fb_page},
            {"label": "FB Inlägg", "url": fb_post},
            {"label": "Karta", "url": map_url, "type": "map"},
        ],
    },
    {
        "id": "motortraffen-garsnas-nationaldag-2026-06-06",
        "name": "Motorträffen - Nationaldagen",
        "date": "2026-06-06",
        "dateEnd": "2026-06-06",
        "type": "Träff",
        "region": "Skåne",
        "location": location,
        "organizer": organizer,
        "description": (
            "Motorträffen firar Sveriges nationaldag. OBS annan dag och tid: lördag kl 16. "
            "Bilar, motorcyklar, mopeder, traktorer m.m."
        ),
        "descriptionFull": (
            "Motorträffen i Gärsnäs firar Sveriges nationaldag.\n\n"
            "OBS: annan dag och tid än vanligt. Lördag 6 juni kl 16.00.\n\n"
            + series_note + "\n\n" + dates_info
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": fb_post,
        "links": [
            {"label": "FB Sida", "url": fb_page},
            {"label": "FB Inlägg", "url": fb_post},
            {"label": "Karta", "url": map_url, "type": "map"},
        ],
    },
    {
        "id": "motortraffen-garsnas-avslutning-2026-09-13",
        "name": "Motorträffen - Avslutning",
        "date": "2026-09-13",
        "dateEnd": "2026-09-13",
        "type": "Träff",
        "region": "Skåne",
        "location": location,
        "organizer": organizer,
        "description": (
            "Säsongsavslutning för motorträffen i Gärsnäs. Söndag kl 12, tipsrunda startar "
            "mellan 12.30 och 13.30."
        ),
        "descriptionFull": (
            "Säsongsavslutning för motorträffen vid grillplatsen bredvid Österlenvulk AB i Gärsnäs. "
            "Söndag 13 september kl 12.00.\n\n"
            "Tipsrundan startar mellan kl 12.30 och 13.30.\n\n"
            + series_note + "\n\n" + dates_info
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": fb_post,
        "links": [
            {"label": "FB Sida", "url": fb_page},
            {"label": "FB Inlägg", "url": fb_post},
            {"label": "Karta", "url": map_url, "type": "map"},
        ],
    },
]

for ev in events_to_add:
    eid = ev['id']
    if any(e.get('id') == eid for e in data['events']):
        print(f'SKIP duplicate: {eid}')
    else:
        data['events'].append(ev)
        print(f'Added: {eid}')

data['events'].sort(key=lambda e: (e.get('date', ''), e.get('id', '')))
data['lastUpdated'] = datetime.utcnow().isoformat() + 'Z'
out = header + json.dumps(data, ensure_ascii=False, indent=6) + ';\n'
with open('events.js', 'w', encoding='utf-8') as f:
    f.write(out)

real = [e for e in data['events'] if not e.get('_canary') and not e.get('_ad')]
print(f"Total: {len(data['events'])} | Real: {len(real)} | Canaries: {len([e for e in data['events'] if e.get('_canary')])} | ADs: {len([e for e in data['events'] if e.get('_ad')])}")
