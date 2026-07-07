#!/usr/bin/env python3
"""
backfill-images.py — events.json のimageUrlを自動補完

優先順位で各イベントの imageUrl を埋める:
  1. instagramUrl / instagramPostId  → 投稿ページの og:image
  2. sourceUrl                        → og:image
  3. url                              → og:image

取得した画像URLは HEAD で生存確認(2xx応答)してから採用。

Usage:
  python3 scripts/backfill-images.py                   # 全件処理
  python3 scripts/backfill-images.py --slug foo-2026   # 1件のみ
  python3 scripts/backfill-images.py --dry-run         # 結果表示のみ(events.jsonは変更しない)
  python3 scripts/backfill-images.py --limit 20        # 最大20件まで処理
  python3 scripts/backfill-images.py --overwrite       # 既にimageUrlがあっても上書きを試みる
"""

import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_JSON = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'events.json'))

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
HEADERS = {'User-Agent': UA, 'Accept-Language': 'ja,en;q=0.8'}
TIMEOUT = 12

# --- Aggregator/blocklist (used by image, url and field acceptance) ---
AGGREGATOR_DOMAINS = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
)
_GENERIC_IMG_RE = re.compile(
    r'/(ogp|ogimage|og_image|og-image|default|logo|sitelogo|share|thumb|main|noimage|placeholder)\.(png|jpg|jpeg|webp|gif)(\?|$)'
    r'|/cropped-',  # WordPressサイトアイコン(favicon)へのフォールバック
    re.I
)
# イベントと無関係なドメインの画像(会場運営元の汎用OGP等)。
# 実例: カシマスタジアム経由で jleague.jp の汎用OGPが混入(2026-07-06検出)
UNRELATED_IMAGE_DOMAINS = ('jleague.jp', 'static.cdninstagram.com', 'mercari')

def _url_contains_aggregator(url):
    """Detect aggregator anywhere in the URL (host or CDN-proxied path)."""
    if not url: return False
    u = url.lower()
    return any(ag in u for ag in AGGREGATOR_DOMAINS)

def is_aggregator_url(url):
    """Reject URLs whose host or path contains a known aggregator domain."""
    return _url_contains_aggregator(url)

def is_quality_image_url(img_url):
    """Image URL acceptance: reject aggregator-sourced / generic-named / unrelated-domain images."""
    if not img_url:
        return False
    if _url_contains_aggregator(img_url):
        return False
    if _GENERIC_IMG_RE.search(img_url):
        return False
    u = img_url.lower()
    if any(d in u for d in UNRELATED_IMAGE_DOMAINS):
        return False
    return True




# --- helpers ----------------------------------------------------------------

def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            return None, f'HTTP {r.status_code}'
        ctype = r.headers.get('Content-Type', '')
        if 'html' not in ctype.lower() and 'xml' not in ctype.lower():
            return None, f'not html ({ctype})'
        # encoding
        if r.encoding is None or r.encoding.lower() == 'iso-8859-1':
            r.encoding = r.apparent_encoding or 'utf-8'
        return r.text, None
    except requests.RequestException as e:
        return None, type(e).__name__

def extract_og_image(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    for prop in ('og:image:secure_url', 'og:image:url', 'og:image'):
        m = soup.find('meta', attrs={'property': prop}) or soup.find('meta', attrs={'name': prop})
        if m and m.get('content'):
            return urljoin(base_url, m['content'].strip())
    # twitter:image fallback
    m = soup.find('meta', attrs={'name': 'twitter:image'}) or soup.find('meta', attrs={'property': 'twitter:image'})
    if m and m.get('content'):
        return urljoin(base_url, m['content'].strip())
    return None

def verify_image(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code >= 400:
            # some CDNs reject HEAD; try a tiny GET
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                             allow_redirects=True, stream=True)
            r.close()
        if r.status_code >= 400:
            return False, f'HTTP {r.status_code}'
        ctype = (r.headers.get('Content-Type') or '').lower()
        if ctype and not ctype.startswith('image/'):
            # accept octet-stream too (some servers)
            if 'octet-stream' not in ctype:
                return False, f'wrong type ({ctype})'
        return True, None
    except requests.RequestException as e:
        return False, type(e).__name__



# --- daybook-botanical (ボタ日誌) からのフライヤー画像取得 -------------------
# Instagramはデータセンター IP からの匿名取得を拒否するため、
# IG発のフライヤーを安定CDN(i0.wp.com)で再配信している daybook の記事を探す。
DAYBOOK = 'https://daybook-botanical.com'

def _date_tokens(ev):
    """記事本文との照合用に「7月10日」等の表記ゆれトークンを作る。"""
    d = ev.get('date') or ''
    if not d:
        return []
    m, day = int(d[5:7]), int(d[8:10])
    return [f'{m}月{day}日', f'{m}/{day}', f'{d[:4]}年{m}月']

def _extract_article_image(html, base_url):
    """記事本文(entry-content)内の最初の実画像を返す。サイトアイコン等は除外。"""
    soup = BeautifulSoup(html, 'html.parser')
    body = None
    for cand in soup.find_all(class_=re.compile(r'(entry-content|post-content|post_content|article-body)')):
        cls = ' '.join(cand.get('class') or [])
        if 'p-toc' in cls:  # SWELLテーマの目次コンテナを除外
            continue
        body = cand
        break
    if body is None:
        return None  # 本文コンテナ不明のページでは拾わない(関連記事サムネ誤用防止)
    for img in body.find_all('img'):
        cand = img.get('data-src') or img.get('src') or ''
        if not cand or cand.startswith('data:'):
            continue
        cand = urljoin(base_url, cand)
        if not is_quality_image_url(cand):
            continue
        # 極小画像(アイコン類)を width/height 属性で除外
        try:
            w = int(img.get('width') or 0)
            if 0 < w < 200:
                continue
        except ValueError:
            pass
        return cand
    return None

def daybook_image(ev):
    """daybookでイベント記事を検索し、日付照合のうえフライヤー画像URLを返す。"""
    name = (ev.get('name') or '').strip()
    if not name:
        return None, 'no name'
    # 検索クエリ: 厳密→単純化の順に試す(年号・回数・括弧書き会場を段階的に除去)
    q1 = re.sub(r'(vol\.?\s*\d+|第\s*\d+\s*回|[#＃]\d+)', '', name, flags=re.I).strip()
    q2 = re.sub(r'(19|20)\d{2}|[（(][^）)]*[）)]|[「」『』]', ' ', q1).strip()
    q2 = re.sub(r'\s+', ' ', q2)
    queries = [q for q in dict.fromkeys([q1, q2]) if len(q) >= 3]
    seen = []
    for q in queries:
        search_url = f'{DAYBOOK}/?s={requests.utils.quote(q)}'
        html, err = fetch_html(search_url)
        if html is None:
            continue
        for u in re.findall(r'href="(' + re.escape(DAYBOOK) + r'/xo_event/[^"]+)"', html):
            if u not in seen:
                seen.append(u)
        if seen:
            break
    if not seen:
        return None, 'no search results'
    tokens = _date_tokens(ev)
    for art_url in seen[:4]:
        art, err = fetch_html(art_url)
        if art is None:
            continue
        # 開催日が本文に含まれる記事だけを同一イベントとみなす(別回の画像誤用防止)
        if tokens and not any(t in art for t in tokens):
            continue
        img = _extract_article_image(art, art_url)
        if img:
            ok, _ = verify_image(img)
            if ok:
                return img, 'OK'
    return None, 'no matching article/image'


def candidate_urls(ev):
    """Yield candidate page URLs in priority order."""
    ig = ev.get('instagramUrl')
    if ig:
        yield ('instagram', ig)
    elif ev.get('instagramPostId'):
        yield ('instagram', f"https://www.instagram.com/p/{ev['instagramPostId']}/")
    if ev.get('sourceUrl'):
        yield ('sourceUrl', ev['sourceUrl'])
    if ev.get('url'):
        yield ('url', ev['url'])

def find_image_for_event(ev):
    # 経路0: daybook (IG発フライヤーの安定ミラー。日付照合付き)
    img, msg = daybook_image(ev)
    if img:
        yield ('daybook', DAYBOOK, img, 'OK')
        return
    else:
        yield ('daybook', DAYBOOK, None, msg)
    for source, page_url in candidate_urls(ev):
        html, err = fetch_html(page_url)
        if html is None:
            yield (source, page_url, None, f'fetch failed: {err}')
            continue
        img = extract_og_image(html, page_url)
        if not img:
            yield (source, page_url, None, 'no og:image')
            continue
        if not is_quality_image_url(img):
            yield (source, page_url, img, 'rejected: aggregator/generic')
            continue
        ok, err = verify_image(img)
        if not ok:
            yield (source, page_url, img, f'verify failed: {err}')
            continue
        yield (source, page_url, img, 'OK')
        return
    return

# --- main -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int, default=0, help='max events to process (0=all)')
    ap.add_argument('--overwrite', action='store_true',
                    help='retry even if imageUrl is already set')
    ap.add_argument('--upcoming-only', action='store_true',
                    help='開催予定(未終了)のイベントのみ処理')
    ap.add_argument('--events', default=EVENTS_JSON)
    args = ap.parse_args()

    with open(args.events, encoding='utf-8') as f:
        events = json.load(f)

    targets = []
    for ev in events:
        if args.slug and ev.get('slug') != args.slug:
            continue
        if not args.overwrite and ev.get('imageUrl'):
            continue
        if args.upcoming_only:
            from datetime import datetime as _dt
            end = ev.get('dateEnd') or ev.get('date') or ''
            if not end or end < _dt.now().strftime('%Y-%m-%d'):
                continue
        if not any(candidate_urls(ev)):
            continue
        targets.append(ev)

    if args.limit:
        targets = targets[:args.limit]

    print(f'Targets: {len(targets)} events to process')
    updated = 0
    failed = 0
    for i, ev in enumerate(targets, 1):
        slug = ev.get('slug', '?')
        print(f'\n[{i}/{len(targets)}] {slug}')
        result = None
        for source, page, img, msg in find_image_for_event(ev):
            print(f'  via {source} ({page[:60]}) → {img or "—"} | {msg}')
            if msg == 'OK':
                result = img
                break
        if result:
            if not args.dry_run:
                ev['imageUrl'] = result
            updated += 1
            print(f'  ✓ imageUrl = {result}')
        else:
            failed += 1
            print('  ✗ no usable image')
        # politeness: small sleep between events
        time.sleep(0.5)

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
