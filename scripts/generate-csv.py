#!/usr/bin/env python3
"""events.json を events.csv に変換 (Excel/Numbers 互換 BOM-UTF8)."""
import os, json, csv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')
OUT_CSV = os.path.join(REPO_ROOT, 'events.csv')

FIELDS = ['slug','name','date','dateEnd','dateDisplay','prefecture','region',
          'location','tags','description','url','imageUrl','status']

def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    with open(OUT_CSV, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for e in events:
            row=[]
            for k in FIELDS:
                v = e.get(k, '')
                if isinstance(v, list): v = '|'.join(v)
                row.append(v)
            w.writerow(row)
    print(f'Wrote {len(events)} rows to events.csv')

if __name__ == '__main__':
    main()
