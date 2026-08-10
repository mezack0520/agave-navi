#!/usr/bin/env python3
"""
sync-index-cards.py — index.html のカードのサムネイル <img> を
events.json の imageUrl と同期させる。

events.json で imageUrl を持つイベントのカードは <img> 入り、
持たないイベントは event-no-image の見た目に統一する。

冪等。既に正しい状態なら何も書き換えない。

Usage:
  python3 scripts/sync-index-cards.py
  python3 scripts/sync-index-cards.py --dry-run
"""

import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, SCRIPT_DIR)
from sitelib import today_jst
EVENTS_JSON = os.path.join(ROOT, 'events.json')
INDEX_HTML = os.path.join(ROOT, 'index.html')


def html_attr_escape(s):
    return (s or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def img_html(image_url, alt, eager=False):
    # 先頭カード(LCP候補)はeager+fetchpriority、それ以外はlazyで初期ロードを軽くする
    perf = 'decoding="async" fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return (f'<div class="event-thumb"><img src="{html_attr_escape(image_url)}" '
            f'alt="{html_attr_escape(alt)}" width="640" height="360" {perf} referrerpolicy="no-referrer" '
            f"onerror=\"this.parentElement.classList.add('event-no-image');this.remove();\""
            f'></div>')


NO_IMG_HTML = '<div class="event-thumb event-no-image"></div>'

# Match the FIRST event-thumb element inside a card (with or without img),
# the card being identified by data-slug="...".
# We'll handle this by finding the card section then replacing within it.

CARD_HEADER_RE = re.compile(
    r'<div class="event-card[^"]*"[^>]*data-slug="(?P<slug>[^"]+)"[^>]*>',
    re.IGNORECASE
)
THUMB_RE = re.compile(
    r'<div class="event-thumb(?:\s+event-no-image)?"(?:\s*>)\s*'
    r'(?:<img\b[^>]*></div>|</div>)',
    re.IGNORECASE
)



def find_card_span(html, start_idx):
    """<div class="event-card" ...> の開始位置から、div入れ子を数えて閉じ位置を返す。"""
    import re as _re
    depth = 0
    i = start_idx
    tag_re = _re.compile(r'<(/?)div\b[^>]*>', _re.I)
    for m in tag_re.finditer(html, start_idx):
        if m.group(1):
            depth -= 1
            if depth == 0:
                return start_idx, m.end()
        else:
            depth += 1
    return start_idx, len(html)


def remove_stale_cards(html, valid_slugs):
    """events.json に存在しないイベントのカードをindex.htmlから除去する(削除イベントの残留防止)。"""
    import re as _re
    removed = []
    while True:
        stale = None
        for m in _re.finditer(r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"', html):
            if m.group(1) not in valid_slugs:
                stale = m
                break
        if not stale:
            break
        s, e = find_card_span(html, stale.start())
        # 直後の空白行も片付ける
        while e < len(html) and html[e] in '\n\r\t ':
            e += 1
        html = html[:s] + html[e:]
        removed.append(stale.group(1))
    return html, removed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    by_slug = {e.get('slug'): e for e in events if e.get('slug')}

    with open(INDEX_HTML, encoding='utf-8') as f:
        html = f.read()
    original_html = html

    # 削除されたイベントのカードを除去(events.jsonが正)
    html, stale_removed = remove_stale_cards(html, set(by_slug.keys()))
    if stale_removed:
        print(f'stale cards removed: {stale_removed}')

    # 終了イベントカードの間引き: 直近12件のみ静的DOMに残す。
    # 全終了カード(168件超)を埋め込むとHTML450KB/DOM4900ノードになり
    # モバイルのパース・レイアウトが重くなるため(2026-07-15 PageSpeed対応)。
    # 古い終了イベントはアーカイブページ(/archive/)で閲覧できる。
    _today = today_jst()  # JSTで判定(UTCだと前日扱いになる)
    KEEP_PAST = 12
    past_cards = []  # (end_date, slug)
    for m in re.finditer(r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"[^>]*>', html):
        slug_m = m.group(1)
        ev_m = by_slug.get(slug_m)
        if not ev_m:
            continue
        end_m = ev_m.get('dateEnd') or ev_m.get('date') or ''
        if end_m and end_m < _today:
            past_cards.append((end_m, slug_m))
    past_cards.sort(reverse=True)
    prune = {s for _, s in past_cards[KEEP_PAST:]}
    if prune:
        html, _removed2 = remove_stale_cards(html, set(by_slug.keys()) - prune)
        print(f'pruned old past cards: {len(prune)} (kept latest {KEEP_PAST})')

    new_chunks = []
    last_end = 0
    swapped_to_img = 0
    swapped_to_noimg = 0
    unchanged = 0
    img_count = 0
    for m in CARD_HEADER_RE.finditer(html):
        # Append everything up to (and including) the card opening tag
        new_chunks.append(html[last_end:m.end()])
        slug = m.group('slug')
        # Find the FIRST <div class="event-thumb..."> after the card open
        thumb_match = THUMB_RE.search(html, m.end())
        if not thumb_match:
            # No thumb? skip
            last_end = m.end()
            continue
        # Append text between card-open and thumb-start
        new_chunks.append(html[m.end():thumb_match.start()])

        ev = by_slug.get(slug)
        img_url = (ev or {}).get('imageUrl') or ''
        ev_name = (ev or {}).get('name', '') or slug

        existing = thumb_match.group(0)
        if img_url:
            new_html = img_html(img_url, ev_name, eager=(img_count == 0))
            img_count += 1
            if existing != new_html:
                if 'event-no-image' in existing:
                    swapped_to_img += 1
                else:
                    # different image? swap
                    swapped_to_img += 1
                new_chunks.append(new_html)
            else:
                unchanged += 1
                new_chunks.append(existing)
        else:
            if existing != NO_IMG_HTML:
                swapped_to_noimg += 1
                new_chunks.append(NO_IMG_HTML)
            else:
                unchanged += 1
                new_chunks.append(existing)
        last_end = thumb_match.end()

    new_chunks.append(html[last_end:])
    new_html = ''.join(new_chunks)

    # 開催予定件数のバッジ。以前は daily.yml のステップが更新していたが、
    # そのステップは build-all.sh(=auto-status-jst.py)より前に走るため
    # 終了に変わる回を数え落とし、さらに sync-events / weekly-enrichment 経由の
    # ビルドでは誰も更新しなかった。build-all.sh に載っているここへ移した。
    up_count = sum(1 for e in events if e.get('status') == 'upcoming')
    new_html, n_badge = re.subn(
        r'(<span class="event-count" id="eventCount">)\d+(件</span>)',
        lambda m: m.group(1) + str(up_count) + m.group(2), new_html)
    print(f'upcoming badge:      {up_count}件 ({n_badge} 箇所)')

    print(f'cards processed:     {swapped_to_img + swapped_to_noimg + unchanged}')
    print(f'  → swapped to img:  {swapped_to_img}')
    print(f'  → swapped to no-image: {swapped_to_noimg}')
    print(f'  → unchanged:       {unchanged}')

    if new_html != original_html:
        if args.dry_run:
            print('(dry-run, not writing)')
        else:
            with open(INDEX_HTML, 'w', encoding='utf-8') as f:
                f.write(new_html)
            print(f'index.html updated.')
    else:
        print('No changes needed.')


if __name__ == '__main__':
    main()
