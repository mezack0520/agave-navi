#!/usr/bin/env python3
"""
image-health-check.py — events.json の imageUrl 全件の死活を見て、無くなった画像のキーを消す。
消した回はアイキャッチの取り直しの対象になる。

消すのは「無い」と言い切った返事(429/5xx 以外の 4xx)だけ(2026-10-22)。
それまでは 5xx・タイムアウトの1回でも消しており、ほぼ毎回1件ずつ外部の画像が
events.json から落ちていた。取り方(HEAD→GET・429/5xx の引き直し)は sitelib.probe_status。

Usage:
  python3 scripts/image-health-check.py [--dry-run]
"""
import argparse, json, os, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')


def is_gone(code):
    """画像が無くなったと言える返事か。429/5xx と接続できない(-1)は相手の一時的な不調でも起きる"""
    return code >= 400 and not sitelib.should_retry_status(code)

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
        futs = {ex.submit(sitelib.probe_status, e['imageUrl'], 10): (i, e) for i, e in with_img}
        for fut in as_completed(futs):
            i, e = futs[fut]
            status = fut.result()
            if is_gone(status):
                dead.append((i, e['slug'], e['imageUrl'], status))
                print(f'  DEAD ({status}): {e["slug"]} ← {e["imageUrl"][:80]}')
            elif status == -1 or status >= 400:
                print(f'  判定不能・残す ({status}): {e["slug"]} ← {e["imageUrl"][:80]}')
    if dead:
        print(f'\n{len(dead)} dead image(s). Clearing imageUrl...')
        if not args.dry_run:
            for i, slug, url, status in dead:
                # キーごと消す(2026-09-12)。None を書くと、取り込み側が書く
                # 空文字と「値が無い」の表現が2通りになる。`is None` や
                # `in e` で書いた検査が片方だけ拾って静かに漏れるので、
                # audit.blank_optional_fields の案内どおり削除に揃える。
                d[i].pop('imageUrl', None)
            with open(EVENTS, 'w', encoding='utf-8') as f:
                json.dump(d, f, ensure_ascii=False, indent=2)
                f.write('\n')
            print('events.json updated.')
    else:
        print('All image URLs alive.')

if __name__ == '__main__':
    main()
