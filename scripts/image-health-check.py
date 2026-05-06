#!/usr/bin/env python3
"""
image-health-check.py — events.json の imageUrl 全件 HEAD チェック。
404/500/タイムアウト等 → null化して再取得対象にする。

Usage:
  python3 scripts/image-health-check.py [--dry-run]
"""
import argparse, json, os, requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

def check(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code >= 400:
            r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True, stream=True)
            r.close()
        return r.status_code
    except Exception as e:
        return f'err:{type(e).__name__}'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    with open(EVENTS, encoding='utf-8') as f:
        d = json.load(f)
    with_img = [(i, e) for i, e in enumerate(d) if e.get('imageUrl')]
    print(f'Checking {len(with_img)} image URLs...')
    dead = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(check, e['imageUrl']): (i, e) for i, e in with_img}
        for fut in as_completed(futs):
            i, e = futs[fut]
            status = fut.result()
            if isinstance(status, str) or status >= 400:
                dead.append((i, e['slug'], e['imageUrl'], status))
                print(f'  DEAD ({status}): {e["slug"]} ← {e["imageUrl"][:80]}')
    if dead:
        print(f'\n{len(dead)} dead image(s). Clearing imageUrl...')
        if not args.dry_run:
            for i, slug, url, status in dead:
                d[i]['imageUrl'] = None
            with open(EVENTS, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
                f.write('\n')
            print('events.json updated.')
    else:
        print('All image URLs alive.')

if __name__ == '__main__':
    main()
