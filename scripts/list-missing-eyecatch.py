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


POST_CODE = re.compile(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)')


def rejected_hint(rows, hint):
    """hint の投稿が scripts/eyecatch-rejected.json でこの回に不採用なら、その理由"""
    m = POST_CODE.search(hint or '')
    if not m:
        return ''
    for r in rows:
        n = POST_CODE.search(r.get('post') or '')
        if n and n.group(1) == m.group(1):
            return r.get('reason') or '(理由なし)'
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', help='igPost / igProfile / web / none')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--counts', action='store_true', help='件数だけ出す')
    args = ap.parse_args()

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    try:
        with open(os.path.join(SCRIPT_DIR, 'eyecatch-rejected.json'), encoding='utf-8') as f:
            rejected = json.load(f).get('items', {})
    except (OSError, ValueError):
        rejected = {}
    today = today_jst()

    out = []
    for e in events:
        if e.get('imageUrl') or is_cancelled(e):
            continue
        d, de = event_span(e)
        if not d or (de or d) < today:
            continue
        kind, hint = classify(e)
        row = {
            'slug': e.get('slug'), 'name': e.get('name'),
            'date': e.get('date'), 'dateEnd': e.get('dateEnd') or e.get('date'),
            'prefecture': e.get('prefecture'),
            'kind': kind, 'hint': hint,
        }
        # 出典の投稿を既に見て捨てた回は印を付ける。開き直しても同じ画像しか出ない。
        # 2026-10-09: Lier.多肉フェスティバル24会場の出典 DdszFGQBiY- は花友フェスタの
        # フライヤーで、一覧からは分からず1枠を使って開いた。主催のプロフィールから
        # その回の告知を探すか、翌日以降に回す
        why = rejected_hint(rejected.get(e.get('slug')) or [], hint) if kind == 'igPost' else ''
        if why:
            row['hintRejected'] = why
        out.append(row)
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
