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
from sitelib import (today_jst, is_recent_past, event_span,
                     PAST_KEEP_DAYS, PAST_KEEP_MAX, PAST_KEEP_LABEL,
                     LONG_RUN_DAYS, no_image_thumb)
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


def no_img_html(ev):
    """画像なし枠。生成は sitelib が単一情報源"""
    return no_image_thumb(ev or {})

# Match the FIRST event-thumb element inside a card (with or without img),
# the card being identified by data-slug="...".
# We'll handle this by finding the card section then replacing within it.

CARD_HEADER_RE = re.compile(
    r'<div class="event-card[^"]*"[^>]*data-slug="(?P<slug>[^"]+)"[^>]*>',
    re.IGNORECASE
)
# 中身の形に依存させない。以前は <img></div> と空の </div> だけを想定していたため、
# 画像なし枠に県名+日付の <span> を入れた瞬間に一致しなくなり、
# 置換されずカードが増殖した(2026-08-24: 202→1816カード)。
# thumb の中に <div> は入らないので、最初の </div> まで貪欲でなく取れば安全。
THUMB_RE = re.compile(
    r'<div class="event-thumb(?:\s+event-no-image)?"\s*>'
    r'(?:(?!<div\b).)*?</div>',
    re.IGNORECASE | re.DOTALL
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

    # 終了イベントカードの間引き。
    # 全終了カード(168件超)を埋め込むとHTML450KB/DOM4900ノードになり
    # モバイルのパース・レイアウトが重くなる(2026-07-15 PageSpeed対応)。
    # 残す範囲は sitelib.PAST_KEEP_DAYS が単一情報源。以前はここが件数(12件)、
    # status-auto.js が日数(14日)で、全日程の26%で食い違っていた(2026-08-20統合)。
    # 件数は異常時の安全弁として上限だけ見る。
    # 古い終了イベントはアーカイブページ(/archive/)で閲覧できる。
    _today = today_jst()  # JSTで判定(UTCだと前日扱いになる)
    past_cards = []  # (end_date, slug)
    keep_slugs = set()
    for m in re.finditer(r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"[^>]*>', html):
        slug_m = m.group(1)
        ev_m = by_slug.get(slug_m)
        if not ev_m:
            continue
        _st, end_m = event_span(ev_m)
        if end_m and end_m < _today:
            past_cards.append((end_m, slug_m))
            if is_recent_past(ev_m, _today):
                keep_slugs.add(slug_m)
    past_cards.sort(reverse=True)
    # 上限を超える分は新しい順に切る
    keep_ordered = [sl for _, sl in past_cards if sl in keep_slugs][:PAST_KEEP_MAX]
    keep_slugs = set(keep_ordered)
    prune = {sl for _, sl in past_cards if sl not in keep_slugs}
    if prune:
        html, _removed2 = remove_stale_cards(html, set(by_slug.keys()) - prune)
        print(f'pruned old past cards: {len(prune)} '
              f'(kept {len(keep_slugs)} = {PAST_KEEP_LABEL}, 上限{PAST_KEEP_MAX})')

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
            _ni = no_img_html(ev)
            if existing != _ni:
                swapped_to_noimg += 1
                new_chunks.append(_ni)
            else:
                unchanged += 1
                new_chunks.append(existing)
        last_end = thumb_match.end()

    new_chunks.append(html[last_end:])
    new_html = ''.join(new_chunks)

    # 終了セクションの見出しに、載っている範囲を明記する。
    # 「終了したイベント」だけでは全件あるように見えるが、実際は
    # sitelib.PAST_KEEP_DAYS で切った直近ぶんしか載っていない。
    def _note(label):
        return f'<span class="section-heading-note">{label}</span>'

    new_html, n_ph = re.subn(
        r'(id="pastEventsHeading">)終了したイベント'
        r'(?:<span class="section-heading-note">[^<]*</span>)?(</h3>)',
        lambda m: m.group(1) + '終了したイベント' + _note(PAST_KEEP_LABEL) + m.group(2),
        new_html)
    new_html, n_oh = re.subn(
        r'(id="ongoingHeading"[^>]*>)開催中'
        r'(?:<span class="section-heading-note">[^<]*</span>)?(</h2>)',
        lambda m: m.group(1) + '開催中' + _note(f'会期{LONG_RUN_DAYS}日以上') + m.group(2),
        new_html)
    print(f'section headings:    終了={n_ph} 開催中={n_oh}')

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
