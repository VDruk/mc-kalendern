#!/usr/bin/env python3
"""Insert Mackaträffen Vollsjö 2026 - opening and closing rally."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/669178684_1363834765776676_8417752571379270012_n.jpg'
dst = 'ads/mackatraffen-vollsjo-back-2026.jpg'
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

fb_link = "https://www.facebook.com/photo/?fbid=1363834759110010&set=a.466300335530128"
fb_page = "https://www.facebook.com/MackatraffenIVollsjo"

events_to_add = [
    {
        "id": "mackatraffen-vollsjo-start-2026-05-03",
        "name": "Mackaträffen - Säsongsstart",
        "date": "2026-05-03",
        "dateEnd": "2026-05-03",
        "type": "Körning",
        "region": "Skåne",
        "location": "Nyvång, Vollsjö",
        "organizer": "Mackaträffen Vollsjö",
        "description": "Säsongsstart för Mackaträffen på Nyvång i Vollsjö. Mackarallyt kl 11-12. Grillkorv, kaffe och kaka. Överskott till välgörande ändamål.",
        "descriptionFull": (
            "Välkommen till Vollsjö på Mackaträffen. "
            "Här finns också grillkorv, kaffe och kaka när du blir sugen. "
            "Överskottet går till välgörande ändamål.\n\n"
            "Start söndag 3 maj rallystart i Mackarallyt kl. 11-12. "
            "Med fortsättning varannan måndag från 11 maj fram till måndag 31 aug.\n\n"
            "Avslutning söndag 13 sept Mackarallyt kl. 11-12."
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": fb_link,
        "links": [
            {"label": "FB Inlägg", "url": fb_link},
            {"label": "FB Sida", "url": fb_page},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=Nyv%C3%A5ng+Vollsj%C3%B6", "type": "map"},
        ],
    },
    {
        "id": "mackatraffen-vollsjo-avslutning-2026-09-13",
        "name": "Mackaträffen - Säsongsavslutning",
        "date": "2026-09-13",
        "dateEnd": "2026-09-13",
        "type": "Körning",
        "region": "Skåne",
        "location": "Nyvång, Vollsjö",
        "organizer": "Mackaträffen Vollsjö",
        "description": "Säsongsavslutning för Mackaträffen på Nyvång i Vollsjö. Mackarallyt kl 11-12. Grillkorv, kaffe och kaka. Överskott till välgörande ändamål.",
        "descriptionFull": (
            "Välkommen till Vollsjö på Mackaträffen. "
            "Här finns också grillkorv, kaffe och kaka när du blir sugen. "
            "Överskottet går till välgörande ändamål.\n\n"
            "Avslutning söndag 13 sept Mackarallyt kl. 11-12.\n\n"
            "Under säsongen har träffar hållits varannan måndag från 11 maj fram till måndag 31 aug."
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": fb_link,
        "links": [
            {"label": "FB Inlägg", "url": fb_link},
            {"label": "FB Sida", "url": fb_page},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=Nyv%C3%A5ng+Vollsj%C3%B6", "type": "map"},
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
