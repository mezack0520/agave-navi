#!/usr/bin/env python3
"""
generate-itemlist-jsonld.py — index.html に upcoming events から動的 ItemList JSON-LD を埋め込む
"""
import json, os, re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
INDEX = os.path.join(ROOT, 'index.html')
DOMAIN = 'https://agave-navi.com'

def html_attr(s): return (s or '').replace('"','\\"')

def main():
    with open(EVENTS, encoding='utf-8') as f:
        d = json.load(f)
    today = date.today().isoformat()
    upcoming = sorted(
        [e for e in d if e.get('status')=='upcoming' and (e.get('dateEnd') or e.get('date') or '') >= today and e.get('slug') and e.get('date')],
        key=lambda e: e.get('date','')
    )[:12]
    items = []
    for i, e in enumerate(upcoming, 1):
        ev_obj = {
            "@type":"ListItem",
            "position": i,
            "item": {
                "@type": "Event",
                "name": e.get('name',''),
                "startDate": e.get('date',''),
                "endDate": e.get('dateEnd') or e.get('date',''),
                "url": f'{DOMAIN}/events/{e["slug"]}.html',
                "eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode",
                "eventStatus":"https://schema.org/EventScheduled",
                "location":{
                    "@type":"Place",
                    "name": e.get('venue',''),
                    "address":{
                        "@type":"PostalAddress",
                        "addressRegion": e.get('prefecture','') or e.get('region',''),
                        "addressCountry":"JP"
                    }
                }
            }
        }
        if e.get('imageUrl'):
            ev_obj['item']['image'] = e['imageUrl']
        items.append(ev_obj)
    payload = {
        "@context":"https://schema.org",
        "@type":"ItemList",
        "name":"アガベ・植物イベント 開催予定",
        "numberOfItems": len(items),
        "itemListElement": items
    }
    new_block = '<script type="application/ld+json" id="dynamic-itemlist">\n' + json.dumps(payload, ensure_ascii=False, indent=2) + '\n</script>'

    with open(INDEX, encoding='utf-8') as f:
        t = f.read()
    # Replace existing dynamic-itemlist if any, else insert before </head>
    new_t, n = re.subn(
        r'<script type="application/ld\+json" id="dynamic-itemlist">.*?</script>',
        new_block, t, count=1, flags=re.DOTALL
    )
    if n == 0:
        new_t = t.replace('</head>', new_block + '\n</head>', 1)
    with open(INDEX, 'w', encoding='utf-8') as f:
        f.write(new_t)
    print(f'index.html: ItemList JSON-LD updated ({len(items)} events)')

if __name__ == '__main__':
    main()
