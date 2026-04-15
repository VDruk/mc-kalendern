#!/usr/bin/env python3
"""Insert 4 new events + update Calles Chopperdelar placeholder.
Events:
  1. CFMOTO Demodag - 2026-04-25, Älmhult
  2. Calles Chopperdelar Öppet Hus - 2026-05-30, Moheda (UPDATE existing)
  3. Mopedens dag - 2026-05-30, Hasselfors
  4. Mopedrally Nyhammar - 2026-06-27, Nyhammar
  5. Mopedrally och bilträff - 2026-05-16, Österbybruk
"""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

def process_image(src, dst):
    im = Image.open(src)
    if im.mode in ('RGBA', 'P'):
        im = im.convert('RGB')
    if im.width != 800:
        new_h = int(round(im.height * 800 / im.width))
        im = im.resize((800, new_h), Image.LANCZOS)
    im.save(dst, 'JPEG', quality=85, optimize=True)
    print('Image saved: ' + dst + ' ' + str(im.size))

# Images
process_image('FB groups and events/671006944_1546338810835193_6536159345664867490_n.jpg',
              'ads/cfmoto-demodag-almhult-back-2026-04-25.jpg')
process_image('FB groups and events/672673525_1563989715727715_615462335023830459_n.jpg',
              'ads/calles-chopperdelar-back-2026-05-30.jpg')
process_image('FB groups and events/669936973_968645778853811_5479740119977633474_n.jpg',
              'ads/mopedens-dag-hasselfors-back-2026-05-30.jpg')
process_image('FB groups and events/662656561_1338668858285890_5102734767460321222_n.jpg',
              'ads/mopedrally-nyhammar-back-2026-06-27.jpg')
process_image('FB groups and events/663234005_1257905473134492_1453122488993391287_n.jpg',
              'ads/mopedrally-osterbybruk-back-2026-05-16.jpg')

with open('events.js', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'const\s+EVENTS_DATA\s*=\s*', content)
header = content[:m.end()]
data = json.loads(content[m.end():].rstrip().rstrip(';').rstrip())

# ── UPDATE existing Calles Chopperdelar placeholder ──────────────────────────
for ev in data['events']:
    if ev.get('id') == 'calles-chopperdelar-event-2026':
        ev['name'] = 'Calles Chopperdelar - Öppet Hus'
        ev['location'] = 'Slätthög 2, 342 63 Moheda'
        ev['description'] = (
            'Öppet hus hos Calles Chopperdelar 30 maj kl 10-15. '
            'MTL Custom visar Indian & Royal Enfield. Attåsson visar sin Knucklewood. '
            'Pris snyggaste hoj, hamburgare, rabatterade priser, lotteri.'
        )
        ev['descriptionFull'] = (
            'Varmt välkomna till vårt Öppet hus!\n\n'
            'Kl. 10.00-15.00 på Slätthög 2, 342 63 Moheda.\n\n'
            'MTL Custom kommer och visar upp Indian & Royal Enfield.\n'
            'Attåsson visar upp sin Knucklewood.\n\n'
            'Dessutom:\n'
            'Pris till snyggaste hojen på parkeringen\n'
            'Hamburgare för hungriga\n'
            'Rabatterade priser\n'
            'Lotteri och mycket mer!\n\n'
            'Calles Chopperdelar - din helhetsleverantör av mc- & chopperdelar sedan 1975.'
        )
        ev['link'] = 'https://www.facebook.com/events/3228363040678656'
        # Update links: replace generic Facebook link with FB Event
        ev['links'] = [
            {'label': 'FB Event', 'url': 'https://www.facebook.com/events/3228363040678656'},
            {'label': 'Webb', 'url': 'https://calleschopperdelar.com'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Sl%C3%A4tth%C3%B6g+2+Moheda', 'type': 'map'},
        ]
        print('Updated: calles-chopperdelar-event-2026')
        break

# ── NEW EVENTS ───────────────────────────────────────────────────────────────
new_events = [
    {
        'id': 'cfmoto-demodag-almhult-2026-04-25',
        'name': 'CFMOTO Demodag',
        'date': '2026-04-25',
        'dateEnd': '2026-04-25',
        'type': 'Show',
        'region': 'Kronoberg',
        'location': 'Torvströvägen 6, 343 33 Älmhult',
        'organizer': 'EuropeanSportsCars AB',
        'description': (
            'Provkör CFMoto-fordon hos EuropeanSportsCars i Älmhult. '
            'Öppet 10-15. Korv, kaffe, fika och godis till barnen. Välkommen!'
        ),
        'descriptionFull': (
            'Välkomna på provkörning av CFMoto 25 April!\n\n'
            'Öppet 10.00-15.00.\n\n'
            'Vi bjuder på korv, kaffe & fika samt godis till barnen. '
            'Kom förbi och provkör våra demofordon från CFMoto.\n\n'
            'EuropeanSportsCars AB\n'
            'Torvströvägen 6, 343 33 Älmhult'
        ),
        'source': 'facebook.com',
        'backImage': 'ads/cfmoto-demodag-almhult-back-2026-04-25.jpg',
        'link': 'https://www.facebook.com/photo/?fbid=1546338804168527&set=a.740322628103486',
        'links': [
            {'label': 'FB Inlägg', 'url': 'https://www.facebook.com/photo/?fbid=1546338804168527&set=a.740322628103486'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Torvstr%C3%B6v%C3%A4gen+6+%C3%84lmhult', 'type': 'map'},
        ],
    },
    {
        'id': 'mopedens-dag-hasselfors-2026-05-30',
        'name': 'Mopedens dag',
        'date': '2026-05-30',
        'dateEnd': '2026-05-30',
        'type': 'Körning',
        'region': 'Örebro',
        'location': 'Bruksgatan 4A, 695 60 Hasselfors',
        'organizer': 'Hasselfors Byalag',
        'description': (
            'Mopeddag i Bruksparken Hasselfors. Backluckeloppis kl 10 (fri entré). '
            'Mopedrallytt kl 11.30, avgift 120 kr inkl korv. Kanal 3 Nöje underhåller.'
        ),
        'descriptionFull': (
            'Kl.10.00 Området öppnar\n'
            'Bakluckeloppis, försäljning av hantverk, lotterier\n'
            '(ingen avgift, ingen föranmälan)\n'
            'Vid frågor ring Caroline 070-5763301\n\n'
            'Kl.11.30 Mopedrallyt startar\n'
            'Startavgift 120 kr (korv m. bröd ingår)\n'
            '3 stationer, 6 frågor och en utslagsfråga.\n'
            'Stort prisbord.\n\n'
            '* Kanal 3 Nöje underhåller på området.\n'
            '* Servering'
        ),
        'source': 'facebook.com',
        'backImage': 'ads/mopedens-dag-hasselfors-back-2026-05-30.jpg',
        'link': 'https://www.facebook.com/events/3405039616322369',
        'links': [
            {'label': 'FB Event', 'url': 'https://www.facebook.com/events/3405039616322369'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Bruksgatan+4A+Hasselfors', 'type': 'map'},
        ],
    },
    {
        'id': 'mopedrally-nyhammar-2026-06-27',
        'name': 'Mopedrally Nyhammar',
        'date': '2026-06-27',
        'dateEnd': '2026-06-27',
        'type': 'Körning',
        'region': 'Dalarna',
        'location': 'Norrbovägen 54, 770 14 Nyhammar',
        'organizer': 'Norrbo Folkets Hus',
        'description': (
            'Mopedrally från Norrbo Folkets Hus. Start kl 11. '
            'Startavgift 150 kr inkl hamburgare och läsk. '
            'Kurt Willard säljer moppedelar på plats.'
        ),
        'descriptionFull': (
            'Start avgift 150 kr, det inkluderar en hamburgare och läsk.\n\n'
            'Start från Folkets hus kl. 11.\n\n'
            'Kurt Willard har försäljning av moppedelar.'
        ),
        'source': 'facebook.com',
        'backImage': 'ads/mopedrally-nyhammar-back-2026-06-27.jpg',
        'link': 'https://www.facebook.com/events/831515036644481',
        'links': [
            {'label': 'FB Event', 'url': 'https://www.facebook.com/events/831515036644481'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Norrbov%C3%A4gen+54+Nyhammar', 'type': 'map'},
        ],
    },
    {
        'id': 'mopedrally-osterbybruk-2026-05-16',
        'name': 'Mopedrally och bilträff',
        'date': '2026-05-16',
        'dateEnd': '2026-05-16',
        'type': 'Körning',
        'region': 'Uppsala',
        'location': 'Dannemoravägen 46, Österbybruk',
        'organizer': 'Österbybruks Folkets Hus',
        'description': (
            'Årligt mopedrally och bilträff i Folkets Park Österbybruk. '
            'Parken öppnar kl 11, mopedrally startar kl 13. Startavgift 100 kr.'
        ),
        'descriptionFull': (
            'Lördag den 16 maj kör vi vårt årliga mopedrally samt bilträff '
            'i Folkets Park Österbybruk!\n\n'
            'Parken öppnar klockan 11 och start för mopedrally är klockan 13.\n\n'
            'Startavgift 100 kr.'
        ),
        'source': 'facebook.com',
        'backImage': 'ads/mopedrally-osterbybruk-back-2026-05-16.jpg',
        'link': 'https://www.facebook.com/events/1104148556109904',
        'links': [
            {'label': 'FB Event', 'url': 'https://www.facebook.com/events/1104148556109904'},
            {'label': 'Karta', 'url': 'https://www.google.com/maps/search/?api=1&query=Dannemorav%C3%A4gen+46+%C3%96sterbybruk', 'type': 'map'},
        ],
    },
]

for ev in new_events:
    eid = ev['id']
    if any(e.get('id') == eid for e in data['events']):
        print('SKIP duplicate: ' + eid)
    else:
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
