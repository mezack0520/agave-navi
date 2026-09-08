#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""events.json の差分を site-updates.json に積む。TOPの更新欄とRSSの元。

## なぜ要るか

一覧サイトの値打ちは「いまの状態が正しいこと」だが、**変わったことは
どこにも出ていなかった**。カードの「新着」バッジは7日で消えるだけで、
中止に至っては受け取り手がいない。詳細ページに中止と出しても、
2週間前に見た人はそのページに戻ってこない(2026-09-08、コレクトプランツで
実際に起きた。主催者から削除依頼が来るまで誰も気づかなかった)。

## 何をニュースとするか

ここを広く採るとノイズで埋まって読まれなくなる。**来場の判断が変わる
ことだけ**を採る。

  listed     掲載した
  cancelled  中止・延期になった
  removed    掲載を取り消した
  date       日程が変わった
  venue      会場が変わった

**採らないもの。**
  - status の upcoming → past（時間が経てば必ず起きる。ニュースではない）
  - 説明文・imageUrl・tags・updatedAt の変化（保守であって、来場の判断は変わらない）
  - dateDisplay だけの変化（date が同じなら表記の揺れを直しただけ）

## 比較のしかた

直前のコミットの events.json（`git show HEAD:events.json`）と、いまの
events.json を slug で突き合わせる。CIは生成のあとにコミットするので、
「このビルドで何が変わったか」がそのまま出る。

同じ (date, kind, slug) は二重に積まない。ローカルとCIで同じビルドが
2回走っても増えない。

Usage:
    python3 scripts/track-updates.py            # 差分を積む
    python3 scripts/track-updates.py --dry-run  # 積まずに出す
    python3 scripts/track-updates.py --self-test
"""
import argparse
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from sitelib import today_jst, is_cancelled, cancel_label   # noqa: E402

EVENTS = os.path.join(REPO, 'events.json')
LOG = os.path.join(REPO, 'site-updates.json')
KEEP = 120          # 保持する件数。フィードは50件まで出す

KIND_LABEL = {
    'listed': '掲載',
    'cancelled': '中止',
    'postponed': '延期',
    'removed': '掲載取り消し',
    'date': '日程変更',
    'venue': '会場変更',
}


def load_prev():
    """直前のコミットの events.json。取れなければ None（初回扱い）"""
    try:
        out = subprocess.run(['git', '-C', REPO, 'show', 'HEAD:events.json'],
                             capture_output=True, text=True, timeout=30)
        if out.returncode != 0:
            return None
        return json.loads(out.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def venue_of(e):
    return (e.get('venue') or e.get('location') or '').strip()


def span_of(e):
    return ((e.get('date') or '').strip(), (e.get('dateEnd') or '').strip())


def diff(prev, cur):
    """(kind, event, detail) の並びを返す"""
    p = {e.get('slug'): e for e in prev if e.get('slug')}
    c = {e.get('slug'): e for e in cur if e.get('slug')}
    out = []

    for slug, e in c.items():
        if slug not in p:
            out.append(('listed', e, ''))
            continue
        was, now = p[slug], e
        # 中止・延期になった（元が中止でなかった回だけ）
        if is_cancelled(now) and not is_cancelled(was):
            kind = 'postponed' if cancel_label(now) == '延期' else 'cancelled'
            out.append((kind, now, (now.get('cancelReason') or '').strip()))
            continue
        # 日程が動いた。dateDisplay だけの違いは見ない
        if span_of(was) != span_of(now):
            a = was.get('dateDisplay') or was.get('date') or ''
            b = now.get('dateDisplay') or now.get('date') or ''
            out.append(('date', now, f'{a} → {b}'))
            continue
        # 会場が動いた
        if venue_of(was) != venue_of(now) and venue_of(was) and venue_of(now):
            out.append(('venue', now, f'{venue_of(was)} → {venue_of(now)}'))

    for slug, e in p.items():
        if slug not in c:
            out.append(('removed', e, ''))
    return out


def load_log():
    try:
        with open(LOG, encoding='utf-8') as f:
            d = json.load(f)
        if isinstance(d, dict):
            return d
    except (OSError, ValueError):
        pass
    return {'_note': '', 'updated': '', 'items': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    with open(EVENTS, encoding='utf-8') as f:
        cur = json.load(f)
    prev = load_prev()
    if prev is None:
        print('直前のevents.jsonが取れないので差分は出さない（初回か履歴なし）')
        return 0

    changes = diff(prev, cur)
    log = load_log()
    seen = {(i.get('on'), i.get('kind'), i.get('slug')) for i in log['items']}
    today = today_jst()
    added = []
    for kind, e, detail in changes:
        key = (today, kind, e.get('slug'))
        if key in seen:
            continue
        seen.add(key)
        added.append({
            'on': today, 'kind': kind, 'slug': e.get('slug'),
            'name': e.get('name') or e.get('slug'),
            'date': e.get('date') or '', 'dateEnd': e.get('dateEnd') or '',
            'prefecture': e.get('prefecture') or '',
            'detail': detail,
        })

    if not added:
        print('新しい差分は無し')
        return 0

    if args.dry_run:
        for a in added:
            print(f"  (dry) {a['on']} {KIND_LABEL.get(a['kind'], a['kind'])} "
                  f"{a['name'][:40]} {a['detail'][:40]}")
        return 0

    log['items'] = (added + log['items'])[:KEEP]
    log['updated'] = today
    log['_note'] = (
        'events.json の差分の記録。scripts/track-updates.py が build-all.sh の'
        '先頭で積む。TOPの更新欄と feeds/updates.xml の元。'
        '来場の判断が変わることだけを採る(掲載/中止/延期/取り消し/日程変更/会場変更)。'
        'status の upcoming→past、説明文・画像・タグの変化は採らない。'
        '広く採るとノイズで埋まって読まれなくなる。'
        f'保持は直近{KEEP}件。')
    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'更新履歴に {len(added)} 件を積んだ（保持 {len(log["items"])} 件）')
    for a in added:
        print(f"    {KIND_LABEL.get(a['kind'], a['kind'])} {a['name'][:44]}")
    return 0


# ---------------------------------------------------------------- self-test
def self_test():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        print(f'  {mark} {label}: {got!r} 期待={want!r}')

    base = {'slug': 'a', 'name': 'イベントA', 'date': '2026-10-01',
            'dateEnd': '2026-10-02', 'venue': 'A会場', 'status': 'upcoming'}

    def one(prev, cur):
        return [(k, d) for k, _, d in diff(prev, cur)]

    print('--- 採るもの ---')
    chk('新しいslug → listed', [k for k, _ in one([], [base])], ['listed'])
    chk('消えたslug → removed', [k for k, _ in one([base], [])], ['removed'])
    cx = dict(base, eventStatus='cancelled', cancelReason='台風')
    chk('中止になった → cancelled', one([base], [cx]), [('cancelled', '台風')])
    px = dict(base, eventStatus='postponed')
    chk('延期になった → postponed', [k for k, _ in one([base], [px])], ['postponed'])
    d2 = dict(base, date='2026-10-08', dateEnd='2026-10-09')
    chk('日程が動いた → date', [k for k, _ in one([base], [d2])], ['date'])
    v2 = dict(base, venue='B会場')
    chk('会場が動いた → venue', [k for k, _ in one([base], [v2])], ['venue'])

    print('\n--- 採らないもの ---')
    chk('status が past になっただけ',
        one([base], [dict(base, status='past')]), [])
    chk('説明文だけ変わった',
        one([base], [dict(base, description='あとから書いた')]), [])
    chk('imageUrl が埋まっただけ',
        one([base], [dict(base, imageUrl='https://x/a.jpg')]), [])
    chk('tags と updatedAt だけ',
        one([base], [dict(base, tags=['アガベ'], updatedAt='2026-09-08')]), [])
    chk('dateDisplay だけの表記直し',
        one([base], [dict(base, dateDisplay='2026.10.01-02')]), [])
    chk('元から中止の回は再掲しない',
        one([cx], [cx]), [])
    chk('会場が空→入った は変更としない（初回登録の埋め）',
        one([dict(base, venue='')], [base]), [])

    print('\n結果: ' + ('すべて通過' if ok else '★失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
