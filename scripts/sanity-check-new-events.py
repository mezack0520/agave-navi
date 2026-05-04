#!/usr/bin/env python3
"""
sanity-check-new-events.py — new-events.json の品質チェック。
明らかに植物イベントでないエントリ(チケット販売系URL等)を除外する。

Usage:
  python3 scripts/sanity-check-new-events.py [--in <path>] [--strict]

--strict: 1件でも reject があれば exit code 1 で失敗
"""
import argparse, json, os, re, sys

# チケット販売・コンサート系ドメイン → 植物イベントの url であるはずがない
TICKETING_DOMAINS = (
    'l-tike.com', 'lawsonticket.com', 'eplus.jp',
    'kyodo-osaka.co.jp', 'kyodo-tokyo.co.jp',
    'pia.jp', 'ticket.rakuten.co.jp', 'cnplayguide',
    'tixee.tv', 'zaiko.io', 'streetdance.jp',
    'fan-club', 'fanclub',
)
# Aggregator (データ汚染源) → 同じく url にしてはいけない
AGGREGATOR_DOMAINS = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net',
)

def url_domain(u):
    m = re.match(r'https?://([^/]+)', (u or '').lower())
    return m.group(1) if m else ''

def reasons(ev):
    rs = []
    url = ev.get('url') or ''
    src = ev.get('sourceUrl') or ''
    full = (url + ' ' + src).lower()
    for d in TICKETING_DOMAINS:
        if d in full:
            rs.append(f'ticketing-domain: {d}')
            break
    for d in AGGREGATOR_DOMAINS:
        if d in full:
            rs.append(f'aggregator-domain: {d}')
            break
    if not ev.get('slug'):
        rs.append('missing slug')
    if not ev.get('name'):
        rs.append('missing name')
    return rs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='new-events.json')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f'No file: {args.inp}'); return 0

    with open(args.inp, encoding='utf-8') as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = [events]

    kept, rejected = [], []
    for ev in events:
        rs = reasons(ev)
        if rs:
            rejected.append((ev.get('slug','?'), ev.get('name','?'), rs))
        else:
            kept.append(ev)

    print(f'Total: {len(events)}, OK: {len(kept)}, Rejected: {len(rejected)}')
    for slug, name, rs in rejected:
        print(f'  REJECT: {slug} ({name}) — {rs}')

    # Overwrite with kept-only
    if rejected:
        with open(args.inp, 'w', encoding='utf-8') as f:
            json.dump(kept, f, ensure_ascii=False, indent=2); f.write('\n')
        print(f'Wrote filtered file: {args.inp}')

    if args.strict and rejected:
        sys.exit(1)

if __name__ == '__main__':
    main()
