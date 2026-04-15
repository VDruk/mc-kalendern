#!/usr/bin/env python3
"""Insert MC-konsult/Zero hos Rapido MC 2026-05-23."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/671612036_1525930572869736_2290856874542709092_n.jpg'
dst = 'ads/mckonsult-rapido-mc-back-2026-05-23.jpg'
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

eid = 'mckonsult-zero-rapido-mc-2026-05-23'
if any(ev.get('id') == eid for ev in data['events']):
    print('SKIP duplicate: ' + eid)
else:
    ev = {
        'id': eid,
        'name': 'MC-konsult / Zero hos Rapido MC',
        'date': '2026-05-23',
        'dateEnd': '2026-05-23',
        'type': 'Show',
        'region': 'Stockholm',
        'location': 'Skansbacken 4, Gullmarsplan, Stockholm',
        'organizer': 'Mc-konsult i Lidköping',
        'description': (
            'Rapido MC bjuder in till sin årliga mc-mässa på Skansbacken i Stockholm. '
            'Mc-konsult tar med provkörningshojar från Zero, Indian & Triumph. Varmt välkommen!'
        ),
        'descriptionFull': (
            'Rapido MC bjuder in till sin årliga mc-mässa på Skansbacken i Stockholm '
            'och vi tar med oss provkörningshojar från Zero, Indian & Triumph. '
            'Varmt välkommen!'
        ),
        'source': 'facebook.com',
        'backImage': dst,
        'link': 'https://www.facebook.com/events/1712245466411015',
        'links': [
            {'label': 'FB Event', 'url': 'https://www.facebook.com/events/1712245466411015'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Skansbacken+4+Gullmarsplan+Stockholm', 'type': 'map'},
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
