#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""staging/eyecatch/ のアイキャッチ候補に採否を書く。

    python3 scripts/apply-eyecatch.py --list
    python3 scripts/apply-eyecatch.py --approve slug-a slug-b
    python3 scripts/apply-eyecatch.py --reject "slug-c=出店者募集の投稿"

候補は CI(ig-organizer-watch.py → eyecatchlib.stage_candidates)が
Business Discovery の原寸画像から作る。**採否は画像を1枚ずつ目で見て決める。**
照合の点数は根拠にならない(eyecatchlib の冒頭)。迷ったら捨てる。

採用: 画像を images/events/<slug>.jpg に移し、imageUrl / imageSource / updatedAt を書く。
不採用: scripts/eyecatch-rejected.json に投稿URLと理由を残す。
        同じ投稿は二度と候補に出ない。同じ主催の別の投稿は出る。
"""
import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402
import eyecatchlib as ec  # noqa: E402

EVENTS_JSON = os.path.join(ec.REPO, 'events.json')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--approve', nargs='*', default=[])
    ap.add_argument('--reject', nargs='*', default=[], help='slug=理由')
    a = ap.parse_args()

    stage = ec.load_json(ec.STAGE_JSON, {'items': {}})
    items = stage.get('items') or {}
    if a.list or not (a.approve or a.reject):
        for sl, it in sorted(items.items(), key=lambda x: x[1].get('date') or ''):
            print(json.dumps({'slug': sl, 'image': f'staging/eyecatch/{sl}.jpg', **it},
                             ensure_ascii=False))
        print(f'候補 {len(items)} 件')
        return 0

    today = sitelib.today_jst()
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    by_slug = {e.get('slug'): e for e in events}
    changed = False
    for sl in a.approve:
        it = items.get(sl)
        src = os.path.join(ec.STAGE_DIR, f'{sl}.jpg')
        if not it or not os.path.exists(src) or sl not in by_slug:
            print(f'✗ {sl}: 候補が無い')
            continue
        os.makedirs(ec.IMG_DIR, exist_ok=True)
        shutil.move(src, os.path.join(ec.IMG_DIR, f'{sl}.jpg'))
        e = by_slug[sl]
        e['imageUrl'] = f'{sitelib.DOMAIN}/images/events/{sl}.jpg'
        e['imageSource'] = it['post']
        e['updatedAt'] = today
        items.pop(sl)
        changed = True
        print(f'✓ {sl}: 採用 ← {it["post"]}')

    rej = ec.load_json(ec.REJECTED_JSON, {})
    rej.setdefault('_note', 'アイキャッチ候補として見て、採らなかった投稿。'
                   'eyecatchlib.stage_candidates はここにある投稿を二度と候補に出さない')
    ritems = rej.setdefault('items', {})
    for arg in a.reject:
        sl, _, reason = arg.partition('=')
        it = items.pop(sl, None)
        if not it:
            print(f'✗ {sl}: 候補が無い')
            continue
        ritems.setdefault(sl, []).append({'post': it['post'], 'reason': reason or '(理由なし)',
                                          'on': today})
        try:
            os.remove(os.path.join(ec.STAGE_DIR, f'{sl}.jpg'))
        except OSError:
            pass
        print(f'– {sl}: 不採用 {reason}')
    if a.reject:
        ec.write_json(ec.REJECTED_JSON, rej)
    ec.write_json(ec.STAGE_JSON, stage)
    if changed:
        with open(EVENTS_JSON, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == '__main__':
    sys.exit(main())
