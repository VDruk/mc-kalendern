#!/usr/bin/env python3
"""Insert Barhäng No Name MC Prospect Chapter Hedemora."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src = 'FB groups and events/670630721_122108611185256710_934255887345600462_n.jpg'
dst = 'ads/nnmc-hedemora-barhang-back-2026-05-09.jpg'
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

eid = 'nnmc-hedemora-barhang-2026-05-09'
if any(ev.get('id') == eid for ev in data['events']):
    print(f'SKIP duplicate: {eid}')
else:
    ev = {
        "id": eid,
        "name": "Barhäng",
        "date": "2026-05-09",
        "dateEnd": "2026-05-09",
        "type": "Fest",
        "region": "Dalarna",
        "location": "Hedemora",
        "organizer": "No Name MC Hedemora",
        "description": "Barhäng hos No Name MC Prospect Chapter Hedemora. Endast SBM och vänner. Start kl 20:00.",
        "descriptionFull": (
            "Barhäng hos No Name MC Prospect Chapter Hedemora.\n\n"
            "Endast SBM och vänner.\n\n"
            "Start kl 20:00."
        ),
        "source": "facebook.com",
        "backImage": dst,
        "link": "https://www.facebook.com/photo/?fbid=122108611179256710&set=a.122101273995256710",
        "links": [
            {"label": "FB Inlägg", "url": "https://www.facebook.com/photo/?fbid=122108611179256710&set=a.122101273995256710"},
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
