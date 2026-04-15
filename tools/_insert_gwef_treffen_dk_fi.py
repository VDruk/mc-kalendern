#!/usr/bin/env python3
"""Insert 2 GWEF Treffen events: Denmark (Nakskov) and Finland (Muonio)."""
import json, re, os
from datetime import datetime
from PIL import Image
os.chdir('/sessions/brave-great-sagan/mnt/mc-events')

src_dk = 'FB groups and events/672167143_1608086880916611_2196329159628454_n.jpg'
dst_dk = 'ads/gwcdk-treffen-back-2026-08-13.jpg'
im = Image.open(src_dk)
if im.mode in ('RGBA', 'P'):
    im = im.convert('RGB')
if im.width != 800:
    new_h = int(round(im.height * 800 / im.width))
    im = im.resize((800, new_h), Image.LANCZOS)
im.save(dst_dk, 'JPEG', quality=85, optimize=True)
print(f'DK image saved: {im.size}')

src_fi = 'FB groups and events/202607.jpg'
dst_fi = 'ads/gwcf-treffen-back-2026-07-23.jpg'
im = Image.open(src_fi)
if im.mode in ('RGBA', 'P'):
    im = im.convert('RGB')
if im.width != 800:
    new_h = int(round(im.height * 800 / im.width))
    im = im.resize((800, new_h), Image.LANCZOS)
im.save(dst_fi, 'JPEG', quality=85, optimize=True)
print(f'FI image saved: {im.size}')

with open('events.js', 'r', encoding='utf-8') as f:
    content = f.read()
m = re.search(r'const\s+EVENTS_DATA\s*=\s*', content)
header = content[:m.end()]
data = json.loads(content[m.end():].rstrip().rstrip(';').rstrip())

events_to_add = [
    {
        "id": "gwcdk-international-treffen-2026-08-13",
        "name": "GWCDK 34th International Treffen",
        "date": "2026-08-13",
        "dateEnd": "2026-08-16",
        "type": "Träff",
        "region": "Danmark",
        "location": "Hestehovedet 2, 4900 Nakskov",
        "organizer": "GoldWing Club Denmark / GWEF",
        "organizerIcon": "clubs/normalized/gwcs.png",
        "description": (
            "GoldWing Club Denmark bjuder in till 34:e internationella treffen vid Nakskov Fjord Camping. "
            "Avgift 490 DKK / 65 € för GWEF-medlemmar, 600 DKK / 80 € för övriga."
        ),
        "descriptionFull": (
            "Welcome to GoldWing Club Denmark's 34th International Treffen in Nakskov, "
            "13-16 August 2026.\n\n"
            "Location: Nakskov Fjord Camping, Hestehovedet 2, 4900 Nakskov, Denmark "
            "(N54.83309, E11.09206).\n\n"
            "Registration: Thursday 12.00-20.00, Friday 9.00-20.00, Saturday 9.00-12.00.\n\n"
            "Treffen fees:\n"
            "GWEF members 490 DKK / 65 EUR\n"
            "Non GWEF members 600 DKK / 80 EUR\n\n"
            "Pre-registration at www.gwef.eu, open from 1 May to 1 July 12.00. "
            "Free t-shirt for pre-registration.\n\n"
            "Treffen fee includes: camping, party tent, live band Friday night, "
            "disco Thursday and Saturday night, trophy presentation Saturday night, "
            "guided tours, national parade, indoor pool, and beach access.\n\n"
            "Extra camping: treffen area open from 10 August. 150 DKK / 20 EUR per person per night, "
            "including electricity (max 400 W).\n\n"
            "Power connection possible (max 400 W per tent). Bring your own cable.\n\n"
            "Food: buffet for Friday and Saturday evenings can be purchased. Food truck open every day.\n\n"
            "Motorhomes, caravans and cabins: book directly with the campsite via "
            "info@nakskovfjordcamping.dk or +45 54 95 17 47.\n\n"
            "Treffen runs under GWEF rules. Contact: international@gwc.dk"
        ),
        "source": "gwef.eu",
        "backImage": dst_dk,
        "link": "https://www.gwef.eu",
        "links": [
            {"label": "gwef.eu", "url": "https://www.gwef.eu"},
            {"label": "GWC Denmark", "url": "https://www.gwc.dk"},
            {"label": "Nakskov Fjord Camping", "url": "https://www.nakskovfjordcamping.dk"},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=Hestehovedet+2+Nakskov", "type": "map"},
        ],
    },
    {
        "id": "gwcf-treffen-muonio-2026-07-23",
        "name": "GWCF Treffen Muonio",
        "date": "2026-07-23",
        "dateEnd": "2026-07-26",
        "type": "Träff",
        "region": "Finland",
        "location": "Harrinivantie 35, 99300 Muonio",
        "organizer": "Gold Wing Club Finland / GWEF",
        "organizerIcon": "clubs/normalized/gwcs.png",
        "description": (
            "Gold Wing Club Finland bjuder in till treffen vid Harriniva Adventure Resort i Muonio, Lappland. "
            "Avgift 70 € för medlemmar, 85 € för övriga. Härifrån startar Polar Nordkapp Tour 2026."
        ),
        "descriptionFull": (
            "Welcome to the Gold Wing Club Finland Treffen, 23-26 July 2026, in Muonio, Lapland.\n\n"
            "Treffen reception opens on Thursday at 12.00.\n\n"
            "Treffen fee: members 70 €, non members 85 €.\n\n"
            "The treffen fee includes, among other things: t-shirt (for those who pre-register), "
            "camping accommodation, sauna access every day, a parade ride, and karaoke.\n\n"
            "Pre-registration opens on 1 January 2026 and closes on 30 June 2026 via www.gwef.eu.\n\n"
            "Venue: Harriniva Adventure Resort, Harrinivantie 35, 99300 Muonio "
            "(67°55'59.7\"N 23°39'24.0\"E), on the banks of the Tornio-Muonio River.\n\n"
            "The parade ride heads into the landscapes of the Pallas fells. "
            "The Olympic flame for the 1952 Olympic Games was lit at Taivaskero, one of the peaks.\n\n"
            "From this treffen, the Polar Nordkapp Tour 2026 will officially start.\n\n"
            "Harriniva prices (per night):\n"
            "Standard Room, 1-2 persons: 120 €\n"
            "Wilderness Room, 2 persons: 140 €\n"
            "Wilderness Room with Loft, 3 persons: 180 €\n"
            "Sauna Room, 2 persons: 160 €\n"
            "Arctic Glass Suite, 2 persons: 280 € (private sauna)\n"
            "Riverside Cabin, 4 persons: 240 € (private sauna)\n\n"
            "Hotel rooms include breakfast, bed linen, and access to shared sauna sessions "
            "(separate times for women and men). Cabins include bed linen and private sauna. "
            "Extra bed available at additional cost.\n\n"
            "Camping is included in the rally fee. Limited electricity at 10 € per tent "
            "(Thursday-Sunday). Campers have access to service building with toilets and showers. "
            "Riverside saunas heated every evening.\n\n"
            "Breakfast buffet (if not included) and dinner Thursday and Friday can be "
            "pre-booked at discounted price.\n\n"
            "Available at extra cost: white-water rafting from Harriniva (approx 1.5 hrs), "
            "Arctic Sauna World by Lake Jerisjärvi (approx 3 hrs, bring swimwear, transport included), "
            "reindeer farm visit at Torassieppi (approx 1 hr, bus included).\n\n"
            "Bookings: https://app.moder.fi/harriniva-hotels-and-safaris or +358 400 155 110. "
            "Use booking code \"GoldWing\".\n\n"
            "Contacts: Interrep Krister Illman +358 40 040 1998 / interrep@gwcf.fi, "
            "Erja Santala +358 40 527 57 97 / sihteeri@gwcf.fi. "
            "Organizers: Erja and Markku Santala, with local experts Anne and Ismo Mäkinen, "
            "and Seppo Jesiöjärvi. Treffen runs under GWEF rules."
        ),
        "source": "gwef.eu",
        "backImage": dst_fi,
        "link": "https://www.gwef.eu",
        "links": [
            {"label": "gwef.eu", "url": "https://www.gwef.eu"},
            {"label": "GWC Finland", "url": "https://www.gwcf.fi"},
            {"label": "Harriniva", "url": "https://www.harriniva.fi"},
            {"label": "Boka", "url": "https://app.moder.fi/harriniva-hotels-and-safaris"},
            {"label": "Karta", "url": "https://www.google.com/maps/search/?api=1&query=Harrinivantie+35+Muonio", "type": "map"},
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
