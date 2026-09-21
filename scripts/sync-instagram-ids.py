#!/usr/bin/env python3
"""sync-instagram-ids.py — imageSource の Instagram 投稿IDを instagramPostId に写す。

    python3 scripts/sync-instagram-ids.py            # 書く
    python3 scripts/sync-instagram-ids.py --dry-run  # 出すだけ
    python3 scripts/sync-instagram-ids.py --self-test

アイキャッチを取ると `imageSource` にその投稿URLが入る。だが
`instagramPostId` は別経路(enrich_events / 手入力)でしか入らないため、
**同じ投稿を指す値が片方にしか無い回が95件たまっていた。**
片方にしか無いと:

  - 詳細頁の埋め込みが出ない(make_instagram_section は投稿IDで判断する)
  - audit.instagram_embed_missing の監視下にも入らない。
    あの検査は「IGの値がある回」だけを見るので、値が無い回は素通りする。
    **見えていないものは壊れても鳴らない。**

写すのは投稿IDだけにする。`instagramUrl` は make_instagram_section が
投稿IDから組み立てるので、両方に持つと必ず片方だけ直して食い違う。

**除外する回**は scripts/eyecatch-review.json に載っているもの。
あそこは「画像の出所がその回の告知投稿ではない」と目視で分かった回
(出店者募集・出店者紹介・会場図・店内写真)。埋め込みは頁の上で
「この回のInstagram投稿」と名乗るので、出所の確度が低いまま載せない。
画像は既に載っているが、画像は出典脚注付きの引用で、埋め込みは名乗りである。

build-all.sh の生成より前で呼ぶ。events.json を書き換えるので、
detail頁の生成はこの後でなければ反映されない。
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
REVIEW = os.path.join(ROOT, 'scripts', 'eyecatch-review.json')


def excluded_slugs(path=REVIEW):
    """出所がその回の告知投稿ではないと分かっている回。"""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, ValueError):
        return set()
    return {i.get('slug') for i in data.get('items', []) if i.get('slug')}


def plan(events, skip):
    """(slug, 投稿ID) の並びを返す。書かない。"""
    out = []
    for ev in events:
        if (ev.get('instagramPostId') or '').strip():
            continue
        src = (ev.get('imageSource') or '').strip()
        if not src:
            continue
        m = sitelib.IG_POST_RE.search(src)
        if not m:
            continue
        if ev.get('slug') in skip:
            continue
        out.append((ev.get('slug'), m.group(1)))
    return out


def self_test():
    skip = {'ng'}
    events = [
        {'slug': 'a', 'imageSource': 'https://www.instagram.com/p/ABC123/'},
        {'slug': 'b', 'imageSource': 'https://www.instagram.com/reel/DEF456'},
        {'slug': 'c', 'imageSource': 'https://example.com/flyer.jpg'},
        {'slug': 'd', 'imageSource': ''},
        {'slug': 'e', 'imageSource': 'https://www.instagram.com/p/GHI789/',
         'instagramPostId': 'ALREADY'},
        {'slug': 'ng', 'imageSource': 'https://www.instagram.com/p/JKL012/'},
        {'slug': 'f', 'imageSource': 'https://www.instagram.com/shop_name/'},
    ]
    got = plan(events, skip)
    assert got == [('a', 'ABC123'), ('b', 'DEF456')], got
    assert plan(events, set()) == [('a', 'ABC123'), ('b', 'DEF456'),
                                   ('ng', 'JKL012')]
    # 同じ投稿を複数の回が出典にすることはある(1投稿で3か月分を告知する回)。
    same = [{'slug': 'x', 'imageSource': 'https://www.instagram.com/p/Z/'},
            {'slug': 'y', 'imageSource': 'https://www.instagram.com/p/Z/'}]
    assert plan(same, set()) == [('x', 'Z'), ('y', 'Z')]
    # instagramUrl は触らない
    keep = [{'slug': 'k', 'imageSource': 'https://www.instagram.com/p/Q/',
             'instagramUrl': 'https://www.instagram.com/p/Q/'}]
    assert plan(keep, set()) == [('k', 'Q')]
    assert excluded_slugs('/nonexistent') == set()
    print('sync-instagram-ids self-test: ok (9 assertions)')


def main():
    args = sys.argv[1:]
    if '--self-test' in args:
        self_test()
        return 0
    dry = '--dry-run' in args

    with open(EVENTS, encoding='utf-8') as f:
        data = json.load(f)
    events = data['events'] if isinstance(data, dict) else data
    skip = excluded_slugs()
    todo = plan(events, skip)

    if not todo:
        print('sync-instagram-ids: 写す回なし')
        return 0

    by_slug = {e.get('slug'): e for e in events}
    for slug, pid in todo:
        print(f'  {slug} ← {pid}')
        if not dry:
            by_slug[slug]['instagramPostId'] = pid

    held = [e.get('slug') for e in events
            if e.get('slug') in skip
            and not (e.get('instagramPostId') or '').strip()
            and sitelib.IG_POST_RE.search(e.get('imageSource') or '')]
    if held:
        print(f'  見送り(出所がその回の告知ではない) {len(held)}件: '
              + ', '.join(sorted(held)))

    if dry:
        print(f'sync-instagram-ids: --dry-run / {len(todo)}件')
        return 0

    with open(EVENTS, 'w', encoding='utf-8') as f:
        # 末尾改行は付けない。events.json の他の書き手(auto-status-jst /
        # merge-new-events)が付けないので、付けると毎回1行の差分が出る。
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'sync-instagram-ids: {len(todo)}件に投稿IDを写した')
    return 0


if __name__ == '__main__':
    sys.exit(main())
