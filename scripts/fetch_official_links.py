#!/usr/bin/env python3
"""
fetch_official_links.py
events.jsonのsourceUrlが空のイベントに対して、
DuckDuckGo検索で公式サイトまたは公式Instagramを見つけて自動追記する。

Usage:
  python scripts/fetch_official_links.py           # sourceUrlが空の全イベントを検索
  python scripts/fetch_official_links.py --slug agave-meeting-2026-kobe  # 特定イベントのみ
  python scripts/fetch_official_links.py --dry-run  # 検索だけでevents.jsonを更新しない
"""

import json
import time
import re
import sys
import argparse
from pathlib import Path

try:
    from duckduckgo_search import DDGS
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "duckduckgo_search"])
    from duckduckgo_search import DDGS

# アグリゲーターサイトを除外
SKIP_DOMAINS = [
    'agave-navi.com', 'pukubook.jp', 'greensnap.jp/greensnap',
    'twitter.com', 'x.com', 'facebook.com', 'youtube.com',
    'wikipedia.org', 'amazon.co.jp', 'rakuten.co.jp',
    'yahoo.co.jp/search', 'google.com', 'bing.com',
    'leaf-laboratory.com', 'minna-ta29.com', 'note.com',
]


def search_official(event_name):
    """DuckDuckGoでイベントの公式情報を検索"""
    result = {'url': None, 'instagram': None, 'candidates': []}
    ddgs = DDGS()

    # 1) 公式サイト検索
    try:
        hits = list(ddgs.text(f"{event_name} 公式サイト", max_results=8))
        for h in hits:
            url = h.get('href', '')
            title = h.get('title', '')
            if any(d in url for d in SKIP_DOMAINS):
                continue
            if 'instagram.com' in url:
                if not result['instagram']:
                    m = re.search(r'instagram\.com/([^/?#]+)', url)
                    if m and m.group(1) not in ('p', 'explore', 'reel', 'stories', 'accounts'):
                        result['instagram'] = f"https://www.instagram.com/{m.group(1)}/"
                continue
            result['candidates'].append({'url': url, 'title': title})
            if not result['url']:
                result['url'] = url
    except Exception as e:
        print(f"  [web] error: {e}")

    time.sleep(1.5)

    # 2) Instagram検索
    if not result['instagram']:
        try:
            hits = list(ddgs.text(f"{event_name} Instagram", max_results=5))
            for h in hits:
                url = h.get('href', '')
                if 'instagram.com/' in url:
                    m = re.search(r'instagram\.com/([^/?#]+)', url)
                    if m and m.group(1) not in ('p', 'explore', 'reel', 'stories', 'accounts'):
                        result['instagram'] = f"https://www.instagram.com/{m.group(1)}/"
                        break
        except Exception as e:
            print(f"  [ig] error: {e}")

    time.sleep(1.5)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', help='特定イベントのslugのみ検索')
    parser.add_argument('--dry-run', action='store_true', help='検索だけで保存しない')
    parser.add_argument('--force', action='store_true', help='sourceUrlがあっても再検索')
    args = parser.parse_args()

    events_path = Path(__file__).resolve().parent.parent / 'events.json'
    with open(events_path, 'r', encoding='utf-8') as f:
        events = json.load(f)

    targets = []
    for ev in events:
        if args.slug and ev.get('slug') != args.slug:
            continue
        if not args.force and ev.get('sourceUrl', '').strip():
            continue
        targets.append(ev)

    print(f"検索対象: {len(targets)}件")
    updated = 0

    for i, ev in enumerate(targets):
        name = ev.get('name', ev.get('slug', ''))
        print(f"\n[{i+1}/{len(targets)}] {name}")

        info = search_official(name)

        found = info['url'] or info['instagram']
        source = info['url'] or info['instagram'] or ''

        if found:
            print(f"  => URL: {info['url'] or '(なし)'}")
            print(f"  => IG:  {info['instagram'] or '(なし)'}")
            if info['candidates']:
                print(f"  => 候補: {[c['url'] for c in info['candidates'][:3]]}")

            if not args.dry_run:
                ev['sourceUrl'] = source
                updated += 1
        else:
            print("  => 見つからず")

    if not args.dry_run and updated > 0:
        with open(events_path, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {updated}件のevents.jsonを更新しました")
    else:
        print(f"\nℹ️ 更新: {updated}件 (dry-run: {args.dry_run})")


if __name__ == '__main__':
    main()
