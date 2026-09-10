#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アイキャッチが無い開催予定の回を、取得の手がかりつきで並べる。

scripts/browser/ig-eyecatch.js と対で使う。あちらが取りに行く先を、
こちらが決める。

出力は JSON。kind で経路が分かれる。

    igPost    出典が Instagram の投稿URL。その投稿から直接取れる
    igProfile 出典が Instagram のプロフィール。投稿を探す必要がある
    web       一般サイト。backfill-images.py が既に試して取れなかった回
    none      出典URLが無い

**中止・延期の回と終了した回は出さない。**中止の回は告知画像に
差し替わっているので、取ると中止のお知らせがアイキャッチになる。

Usage:
    python3 scripts/list-missing-eyecatch.py             # 全件
    python3 scripts/list-missing-eyecatch.py --kind igProfile --limit 6
"""
import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import sitelib
from sitelib import today_jst, is_cancelled, event_span   # noqa: E402

IG_HANDLE = re.compile(r'instagram\.com/([A-Za-z0-9_.]+)')
NOT_HANDLE = {'p', 'reel', 'tv', 'explore', 'accounts', 'stories'}


def classify(ev):
    blob = ' '.join(str(ev.get(k) or '') for k in
                    ('url', 'sourceUrl', 'instagramUrl'))
    m = sitelib.IG_POST_RE.search(blob)
    if m:
        return 'igPost', m.group(0) + '/'
    if 'instagram.com' in blob:
        h = (ev.get('organizerIg') or '').strip()
        if not h:
            hm = IG_HANDLE.search(blob)
            h = hm.group(1) if hm else ''
        if h and h not in NOT_HANDLE:
            return 'igProfile', h
        return 'igProfile', ''
    if (ev.get('url') or ev.get('sourceUrl') or '').strip():
        return 'web', (ev.get('url') or ev.get('sourceUrl') or '').strip()
    return 'none', ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', help='igPost / igProfile / web / none')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--counts', action='store_true', help='件数だけ出す')
    args = ap.parse_args()

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    today = today_jst()

    out = []
    for e in events:
        if e.get('imageUrl') or is_cancelled(e):
            continue
        d, de = event_span(e)
        if not d or (de or d) < today:
            continue
        kind, hint = classify(e)
        out.append({
            'slug': e.get('slug'), 'name': e.get('name'),
            'date': e.get('date'), 'dateEnd': e.get('dateEnd') or e.get('date'),
            'prefecture': e.get('prefecture'),
            'kind': kind, 'hint': hint,
        })
    out.sort(key=lambda x: x['date'])

    if args.counts:
        import collections
        c = collections.Counter(x['kind'] for x in out)
        print(json.dumps({'total': len(out), 'byKind': dict(c)},
                         ensure_ascii=False, indent=1))
        return 0

    if args.kind:
        out = [x for x in out if x['kind'] == args.kind]
    if args.limit:
        out = out[:args.limit]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
