#!/usr/bin/env python3
"""Insert APE Vårträff på Malmköpings Bad & Camping 2026."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/635133076_10223849681350154_5864262107195467884_n.jpg'
dst = 'ads/ape-vartraff-malmkoping-back-2026-05-14.jpg'
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

eid = 'ape-vartraff-malmkoping-2026-05-14'
if any(ev.get('id') == eid for ev in data['events']):
    print(f'SKIP duplicate: {eid}')
else:
    ev = {
        "id": eid,
        "name": "APE Vårträff",
        "date": "2026-05-14",
        "dateEnd": "2026-05-17",
        "type": "Träff",
        "region": "Södermanland",
        "location": "Förrådsgatan 15, 642 60 Malmköping",
        "organizer": "APE-träffar Sverige",
        "description": "Weekend-träff för APE TukTuk och 3-hjuliga veteranmopeder på Malmköpings Bad & Camping. Incheckning 14 maj kl 13, utcheckning 17 maj kl 12. Plats/tält 430 kr/dygn.",
        "descriptionFull": (
            "Välkommen till en weekend med umgänge samt härligt APE-häng på Malmköpings Bad & Camping.\n\n"
            "Förrådsgatan 15, 642 60 Malmköping.\n"
            "Koordinater: 59.13938 16.73219\n\n"
            "Pris per plats/tält: 430 kr/dygn inklusive el, samt campingens faciliteter såsom dusch, toaletter, kök mm.\n"
            "Platser: I första hand 116-119 men kan utökas.\n"
            "Incheckning från 13.00\n"
            "Utcheckning fram till 12.00\n\n"
            "Hyra av stuga:\n"
            "2-bädd 7 kvm, TV: 650 kr/dygn\n"
            "2-bädd 10 kvm, TV, kyl, kokplatta: 900 kr/dygn\n\n"
            "För att du med säkerhet skall få en plats så skall du boka före 2026-05-01.\n"
            "Du bokar själv ditt boende på campingen på telefon 0157-21070 vardagar kl 10.00-14.00 hos Cornelia "
            "eller via mail receptionen@malmkopingscamping.se i namnet APE-träff för att få rätt plats. "
            "Campingkort gäller men går bra utan. Förskottsbetalning via faktura med förfallodag 2026-05-07.\n\n"
            "Mat:\n"
            "Hotell Plevnagården, 400 meter\n"
            "Malmköpings Wärdshus, 1 100 meter\n"
            "Hotell Malmköping, 1 200 meter\n"
            "Star Pizzeria, 1 100 meter\n"
            "Pizzeria Venecia, 1 300 meter\n\n"
            "Läs mer om campingen på: www.malmkopingscamping.se\n"
            "Frågor via E-post till APE-träffgruppen: apetraffar@gmail.com\n"
            "Facebook: Ape-träffar i Sverige och internationellt\n"
            "Mobiltelefon: +46703095513\n\n"
            "\"Tullis\" APE-träff gruppen"
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": "https://www.facebook.com/events/26368659906105627",
        "links": [
            {"label": "FB Event", "url": "https://www.facebook.com/events/26368659906105627"},
            {"label": "malmkopingscamping.se", "url": "https://www.malmkopingscamping.se"},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=F%C3%B6rr%C3%A5dsgatan+15+Malmk%C3%B6ping", "type": "map"},
        ],
    }
    data['events'].append(ev)
    print(f'Added: {eid}')

data['events'].sort(key=lambda e: (e.get('date', ''), e.get('id', '')))
data['lastUpdated'] = datetime.utcnow().isoformat() + 'Z'
out = header + json.dumps(data, ensure_ascii=False, indent=6) + ';\n'
with open('events.js', 'w', encoding='utf-8') as f:
    f.write(out)

real = [e for e in data['events'] if not e.get('_canary') and not e.get('_ad')]
print(f"Total: {len(data['events'])} | Real: {len(real)} | Canaries: {len([e for e in data['events'] if e.get('_canary')])} | ADs: {len([e for e in data['events'] if e.get('_ad')])}")
