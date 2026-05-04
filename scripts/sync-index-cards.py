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
EVENTS_JSON = os.path.join(ROOT, 'events.json')
INDEX_HTML = os.path.join(ROOT, 'index.html')


def html_attr_escape(s):
    return (s or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def img_html(image_url, alt):
    return (f'<div class="event-thumb"><img src="{html_attr_escape(image_url)}" '
            f'alt="{html_attr_escape(alt)}" referrerpolicy="no-referrer" '
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    by_slug = {e.get('slug'): e for e in events if e.get('slug')}

    with open(INDEX_HTML, encoding='utf-8') as f:
        html = f.read()

    new_chunks = []
    last_end = 0
    swapped_to_img = 0
    swapped_to_noimg = 0
    unchanged = 0
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
            new_html = img_html(img_url, ev_name)
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

    print(f'cards processed:     {swapped_to_img + swapped_to_noimg + unchanged}')
    print(f'  → swapped to img:  {swapped_to_img}')
    print(f'  → swapped to no-image: {swapped_to_noimg}')
    print(f'  → unchanged:       {unchanged}')

    if new_html != html:
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
