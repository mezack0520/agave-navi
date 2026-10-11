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

## ブラウザで開く回の選び方 (--browser。2026-10-12)

主催がプロアカウント(watch-sources.json の apiStatus == api)なら、CI
(ig-organizer-watch.py → eyecatchlib.stage_candidates)が最新投稿から候補を
staging/eyecatch/ に置く。ブラウザで同じ投稿を開き直すのは二度手間なので、
ブラウザの対象は次の回だけにする。各行の browserWhy に理由が出る。

    personal / unchecked / (watch外)  API で読めない・まだ読んでいない主催
    ciSkipsSource       出典の投稿は CI の取得範囲にあるが、本文が除外語
                        (eyecatchlib._NOT_FLYER: 募集・中止・出店者さま など)を含むので
                        CI は候補に出さない。画像が来場者向けのフライヤーでも永久に出ない
                        (10-12: 多肉園おひさまの日程投稿は別会場の「中止」、
                        坪井健樹園・笠間宿は「出店者募集」の一文で落ちていた)
    ciSourceOutOfRange  出典の投稿が CI の取得範囲(最新投稿)より古い

api の主催で出典が取得範囲にあり除外語も無い回は CI の担当。候補が出ていないのは
staging の上限(eyecatchlib.MAX_PENDING)で日付順に後ろの回が待っているか、動画で
画像が無いかのどちらか。出典の投稿を既に捨てた回(hintRejected)と、
存在しないアカウント(apiStatus == dead)は出さない。igPost を先、igProfile を後に並べる。

Usage:
    python3 scripts/list-missing-eyecatch.py             # 全件
    python3 scripts/list-missing-eyecatch.py --kind igProfile --limit 6
    python3 scripts/list-missing-eyecatch.py --browser --limit 6   # ブラウザで開く回
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
import eyecatchlib as ec   # noqa: E402

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


def ci_view(e, kind, hint, api_status, latest):
    """CI がこの回の出典をどう扱うか。行に足すキーの dict を返す。

    latest は organizer-posts.json の results(handle → {posts: [...]})。
    CI が実際に照合に使うのは取れた回の投稿(画像つき)で、ここに残るのは本文と URL だけ。
    だから判定できるのは「取得範囲にあるか」と「本文の除外語」までで、動画かどうかは分からない。
    """
    out = {}
    # CI(stage_candidates)は organizerIg で投稿を引く。igProfile で organizerIg が無い回は
    # 出典URLのハンドル(hint)で状態だけ見る
    h = (e.get('organizerIg') or (hint if kind == 'igProfile' else '') or '').strip().lstrip('@').lower()
    st = api_status.get(h, '') if h else ''
    out['apiStatus'] = st or '(watch外)'
    if st != 'api' or kind != 'igPost':
        return out
    code = ec.source_post_code(e)
    posts = (latest.get(h) or {}).get('posts')
    if not code or posts is None:
        return out
    hit = [p for p in posts if ec.post_code(p.get('permalink')) == code]
    if not hit:
        out['ciSourceOutOfRange'] = True
        return out
    cap = ec._n(hit[0].get('caption'))
    words = [w for w in ec._NOT_FLYER if w in cap]
    if words:
        out['ciSkipsSource'] = words
    return out


def browser_why(row):
    """ブラウザで開く理由。対象外なら空(冒頭の「ブラウザで開く回の選び方」)"""
    if row['kind'] not in ('igPost', 'igProfile') or row.get('hintRejected'):
        return ''
    st = row.get('apiStatus')
    if st in ('personal', 'unchecked', '(watch外)'):
        return st
    if st == 'api' and row.get('ciSkipsSource'):
        return 'ciSkipsSource'
    if st == 'api' and row.get('ciSourceOutOfRange'):
        return 'ciSourceOutOfRange'
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kind', help='igPost / igProfile / web / none')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--counts', action='store_true', help='件数だけ出す')
    ap.add_argument('--browser', action='store_true',
                    help='ブラウザで開く回だけ(igPost を先に)。冒頭の選び方を参照')
    args = ap.parse_args()

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    try:
        with open(os.path.join(SCRIPT_DIR, 'eyecatch-rejected.json'), encoding='utf-8') as f:
            rejected = json.load(f).get('items', {})
    except (OSError, ValueError):
        rejected = {}
    ws = ec.load_json(os.path.join(REPO, 'watch-sources.json'), {})
    api_status = {(a.get('handle') or '').strip().lstrip('@').lower(): a.get('apiStatus') or ''
                  for a in (ws.get('igAccounts') or [])}
    latest = ec.load_json(os.path.join(REPO, 'organizer-posts.json'), {}).get('results') or {}
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
        if kind in ('igPost', 'igProfile'):
            row.update(ci_view(e, kind, hint, api_status, latest))
            bw = browser_why(row)
            if bw:
                row['browserWhy'] = bw
        out.append(row)
    out.sort(key=lambda x: x['date'])

    if args.counts:
        import collections
        c = collections.Counter(x['kind'] for x in out)
        b = collections.Counter(x['browserWhy'] for x in out if x.get('browserWhy'))
        print(json.dumps({'total': len(out), 'byKind': dict(c),
                          'browser': sum(b.values()), 'browserByWhy': dict(b)},
                         ensure_ascii=False, indent=1))
        return 0

    if args.browser:
        out = [x for x in out if x.get('browserWhy')]
        out.sort(key=lambda x: (x['kind'] != 'igPost', x['date']))
    if args.kind:
        out = [x for x in out if x['kind'] == args.kind]
    if args.limit:
        out = out[:args.limit]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
