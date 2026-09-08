#!/usr/bin/env python3
"""events.json を events.csv に変換 (Excel/Numbers 互換 BOM-UTF8)."""
import os, json, csv
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import is_cancelled

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
            # 中止の回は配布データから外す。CSVは「開催されるもの」の一覧として
            # 二次利用されるため、中止を混ぜると転載先で開催予定として出回る
            if is_cancelled(e):
                continue
            row=[]
            for k in FIELDS:
                v = e.get(k, '')
                if isinstance(v, list): v = '|'.join(v)
                row.append(v)
            w.writerow(row)
    n = sum(1 for e in events if not is_cancelled(e))
    print(f'Wrote {n} rows to events.csv')

if __name__ == '__main__':
    main()
