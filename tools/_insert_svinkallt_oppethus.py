#!/usr/bin/env python3
"""Insert Svinkallt MC Öppet Hus 2026-04-24."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/672689437_1990926088408140_5869613122740890152_n (1).jpg'
dst = 'ads/svinkallt-mc-oppethus-back-2026-04-24.jpg'
im = Image.open(src)
if im.mode in ('RGBA', 'P'):
    im = im.convert('RGB')
if im.width != 800:
    new_h = int(round(im.height * 800 / im.width))
    im = im.resize((800, new_h), Image.LANCZOS)
im.save(dst, 'JPEG', quality=85, optimize=True)
print('Image saved: ' + str(im.size))

with open('events.js', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'const\s+EVENTS_DATA\s*=\s*', content)
header = content[:m.end()]
data = json.loads(content[m.end():].rstrip().rstrip(';').rstrip())

eid = 'svinkallt-mc-oppethus-2026-04-24'
if any(ev.get('id') == eid for ev in data['events']):
    print('SKIP duplicate: ' + eid)
else:
    ev = {
        'id': eid,
        'name': 'Öppet Hus',
        'date': '2026-04-24',
        'dateEnd': '2026-04-24',
        'type': 'Träff',
        'region': 'Norrbotten',
        'location': 'Industrivägen 2, 981 38 Kiruna',
        'organizer': 'Svinkallt MC',
        'description': (
            'Öppet hus på Svinkallt MC klubbhus i Kiruna. Kl 19:00. '
            'Träffa medlemmarna, kolla klubbhuset, prata MC och gemenskap. Alla är välkomna!'
        ),
        'descriptionFull': (
            '24 April kör vi öppet hus. Kika förbi!\n\n'
            'Datum: 24 april 2026\n'
            'Tid: 19:00 - stängning\n'
            'Plats: Svinkallt MC Klubbhus, Industrivägen 2, Kiruna\n\n'
            'Träffa medlemmarna\n'
            'Kolla klubbhuset\n'
            'Prata MC & gemenskap\n'
            'Alla är välkomna!\n\n'
            'Respekt · Gemenskap · Frihet\n\n'
            'Webb: svinkalltmc.com'
        ),
        'source': 'facebook.com',
        'backImage': dst,
        'link': 'https://www.facebook.com/photo/?fbid=1990926085074807&set=a.676017283232367',
        'links': [
            {'label': 'FB Inlägg', 'url': 'https://www.facebook.com/photo/?fbid=1990926085074807&set=a.676017283232367'},
            {'label': 'FB Sida', 'url': 'https://www.facebook.com/profile.php?id=100024723055154'},
            {'label': 'svinkalltmc.com', 'url': 'https://www.svinkalltmc.com'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Industriv%C3%A4gen+2+Kiruna', 'type': 'map'},
        ],
    }
    data['events'].append(ev)
    print('Added: ' + eid)

data['events'].sort(key=lambda e: (e.get('date', ''), e.get('id', '')))
data['lastUpdated'] = datetime.utcnow().isoformat() + 'Z'
out = header + json.dumps(data, ensure_ascii=False, indent=6) + ';\n'
with open('events.js', 'w', encoding='utf-8') as f:
    f.write(out)

real = [e for e in data['events'] if not e.get('_canary') and not e.get('_ad')]
print('Total: ' + str(len(data['events'])) + ' | Real: ' + str(len(real)) +
      ' | Canaries: ' + str(len([e for e in data['events'] if e.get('_canary')])) +
      ' | ADs: ' + str(len([e for e in data['events'] if e.get('_ad')])))
