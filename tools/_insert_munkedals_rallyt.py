#!/usr/bin/env python3
"""Insert Munkedals Rallyt 2026."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/627350334_10162529961622399_4438685063469322747_n.jpg'
dst = 'ads/munkedals-rallyt-back-2026-05-09.jpg'
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

eid = 'munkedals-rallyt-2026-05-09'
if any(ev.get('id') == eid for ev in data['events']):
    print(f'SKIP duplicate: {eid}')
else:
    ev = {
        "id": eid,
        "name": "Munkedals Rallyt",
        "date": "2026-05-09",
        "dateEnd": "2026-05-09",
        "type": "Körning",
        "region": "Västra Götaland",
        "location": "Parkvägen 8, Munkedal",
        "organizer": "Monk Valley Blue Smoke",
        "description": "Rally runt Munkedal vid sjöar och havet, drygt 9 mil (kortare tur finns). Start kl 09:00 vid Folkets Park. Smörgås före, soppa efter. Startavgift 150 kr.",
        "descriptionFull": (
            "Ett litet rally runt om i Munkedal vid sjöar och havet. "
            "Rundan blir drygt 9 mil. Finns även en kortare tur. "
            "Det blir både asfalt och grusvägar. "
            "Det blir ett litet stopp på vägen där det blir kaffe/dricka och kaka.\n\n"
            "Parkering finns på gamla bandyplan mitt emot parken. "
            "Det blir smörgås före rallyt i parken och soppa efter.\n\n"
            "Startavgift 150 kr betalas till parken i kafét. "
            "Kommer även finnas skamkärra.\n\n"
            "Varmt välkomna!"
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": "https://www.facebook.com/events/886453710795041/",
        "links": [
            {"label": "FB Event", "url": "https://www.facebook.com/events/886453710795041/"},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=Parkv%C3%A4gen+8+Munkedal", "type": "map"},
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
