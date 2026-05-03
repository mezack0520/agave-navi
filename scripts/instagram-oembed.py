#!/usr/bin/env python3
"""
instagram-oembed.py — Instagram oEmbed APIを使ってInstagram投稿の画像URLを取得

events.json の events のうち、imageUrl が空で
instagramUrl もしくは instagramPostId を持つものを処理。

要件: Facebook(Meta) Graph API のアクセストークン
  必要権限: oembed_read
  環境変数 IG_OEMBED_TOKEN にセット (App ID + '|' + App Secret 形式でもOK)
  詳細: docs/instagram-oembed-setup.md

Usage:
  IG_OEMBED_TOKEN=xxx python3 scripts/instagram-oembed.py
  IG_OEMBED_TOKEN=xxx python3 scripts/instagram-oembed.py --slug foo-2026
  IG_OEMBED_TOKEN=xxx python3 scripts/instagram-oembed.py --dry-run
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urlencode

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_JSON = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'events.json'))

OEMBED_ENDPOINT = 'https://graph.facebook.com/v23.0/instagram_oembed'
TIMEOUT = 12

def normalize_post_url(url_or_id):
    """Return canonical instagram post URL from either a full URL or just a post ID"""
    if not url_or_id:
        return None
    # Already a URL
    m = re.match(r'^https?://(www\.)?instagram\.com/(p|reel|tv)/([A-Za-z0-9_-]+)/?', url_or_id)
    if m:
        return f'https://www.instagram.com/{m.group(2)}/{m.group(3)}/'
    # Just an ID
    if re.match(r'^[A-Za-z0-9_-]+$', url_or_id):
        return f'https://www.instagram.com/p/{url_or_id}/'
    return None

def fetch_oembed(post_url, token):
    params = {
        'url': post_url,
        'access_token': token,
        'omitscript': 'true',
        'maxwidth': 1080,
    }
    try:
        r = requests.get(OEMBED_ENDPOINT, params=params, timeout=TIMEOUT)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}: {r.text[:200]}'
        data = r.json()
        thumb = data.get('thumbnail_url')
        if not thumb:
            return None, 'no thumbnail_url in response'
        return thumb, None
    except requests.RequestException as e:
        return None, type(e).__name__
    except json.JSONDecodeError:
        return None, 'invalid JSON response'

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--overwrite', action='store_true')
    ap.add_argument('--events', default=EVENTS_JSON)
    args = ap.parse_args()

    token = os.environ.get('IG_OEMBED_TOKEN')
    if not token:
        print('Error: IG_OEMBED_TOKEN env var not set.', file=sys.stderr)
        print('See docs/instagram-oembed-setup.md for setup instructions.', file=sys.stderr)
        sys.exit(2)

    with open(args.events, encoding='utf-8') as f:
        events = json.load(f)

    targets = []
    for ev in events:
        if args.slug and ev.get('slug') != args.slug:
            continue
        if not args.overwrite and ev.get('imageUrl'):
            continue
        url = normalize_post_url(ev.get('instagramUrl')) or normalize_post_url(ev.get('instagramPostId'))
        if not url:
            continue
        targets.append((ev, url))

    if args.limit:
        targets = targets[:args.limit]

    print(f'Targets: {len(targets)} events with Instagram post URL')
    updated = failed = 0
    for i, (ev, url) in enumerate(targets, 1):
        slug = ev.get('slug', '?')
        print(f'\n[{i}/{len(targets)}] {slug} → {url}')
        thumb, err = fetch_oembed(url, token)
        if thumb:
            print(f'  ✓ {thumb}')
            if not args.dry_run:
                ev['imageUrl'] = thumb
            updated += 1
        else:
            print(f'  ✗ {err}')
            failed += 1
        time.sleep(0.4)

    print(f'\n=== Result ===')
    print(f'Targets : {len(targets)}')
    print(f'Updated : {updated}')
    print(f'Failed  : {failed}')

    if not args.dry_run and updated:
        with open(args.events, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'Wrote {args.events}')

if __name__ == '__main__':
    main()
