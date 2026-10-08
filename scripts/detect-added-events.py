#!/usr/bin/env python3
"""detect-added-events.py — 直近24時間で増えた回を new-events-added.json に書く。

**2026-09-10 に health.yml から出した。**24時間ぶんの差分計算を YAML に
直書きしていたので、ローカルで確かめられず、比較元が取れない回に
どう振る舞うのかもコードを読まないと分からなかった。

比較元は「24時間以内に events.json を触った最古のコミットの親」。
その窓に何も無ければ `HEAD~1`。

**比較元が取れない回は addedDate で代用する(2026-10-09)。**以前は増分ゼロにしていた
(全件を新規として通知に流すより安全、という理由)。ところが 10-07 と 10-09 の health で
浅い clone を深くする fetch が exit 128 で落ち、比較元が取れず掲載0件になり、
**ほかに載せることが無い日はメールそのものが送られなかった**(10-09 は44件を掲載した日)。
addedDate は追加した日を持つので、今日(JST)に足した回だけを出す。昨日の分を入れると前日のメールと
重なる(朝のタスクの掲載は前日のメールに載っている)。昨日の午後に足した回は代用の日だけ落ちる。
代用した回は出力に `fallback` と理由を書き、メールの「残っていること」に1行出す(黙って代用しない)。

  python3 scripts/detect-added-events.py [--out new-events-added.json]
  python3 scripts/detect-added-events.py --self-test
"""
import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import today_jst   # noqa: E402  「今日」は sitelib が単一情報源

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ('slug', 'name', 'date', 'dateEnd', 'location', 'prefecture')


def _git(args):
    return subprocess.check_output(['git'] + args, cwd=REPO,
                                   stderr=subprocess.DEVNULL).decode()


def ensure_history(days=3):
    """浅い clone なら、比較の窓を覆うところまで履歴を足す。

    health.yml は fetch-depth: 10 で checkout する。ところが CI の自動コミットは
    1日に15〜20本あり、24時間の窓が10本に収まらない。浅い clone の境界の
    コミットは「ツリー全体を足した」ように見えるので、それが窓の最古として選ばれ、
    親が無くて比較元が取れず、**その日の掲載がメールから黙って消えていた**
    (2026-10-01 に depth 10 の clone で再現。実際は2件増えていて結果は0件)。
    workflow の深さに頼らず、ここで足す。
    """
    try:
        if _git(['rev-parse', '--is-shallow-repository']).strip() != 'true':
            return None
    except Exception as ex:                         # noqa: BLE001
        return f'rev-parse: {ex}'
    # 10-07・10-09 は --shallow-since が「fatal: error processing shallow info: 4」(exit 128)で落ちた
    # (runner の git 2.55。10-08 は通った)。同じ回に --deepen=300 は通ったので、こちらを先に使う。
    # 300本あれば CI の自動コミット(1日15〜20本)で2週間ぶんを覆う。落ちたら次の深め方で引き直し、
    # 全部落ちたら理由を返す(2026-10-09)
    errs = []
    for opt in ('--deepen=300', f'--shallow-since={days} days ago', '--unshallow'):
        try:
            r = subprocess.run(['git', 'fetch', '--quiet', opt, 'origin'], cwd=REPO, timeout=300,
                               capture_output=True, text=True)
        except Exception as ex:                     # noqa: BLE001
            errs.append(f'{opt}: {ex}')
            continue
        if r.returncode == 0:
            if errs:
                print('detect-added-events: 引き直しで履歴を足した: ' + ' / '.join(errs),
                      file=sys.stderr)
            return None
        tail = (r.stderr or '').strip().splitlines()
        errs.append(f'{opt}: exit {r.returncode} {tail[-1] if tail else ""}'.strip())
    uniq = []
    for x in errs:
        if x not in uniq:
            uniq.append(x)
    msg = ' / '.join(uniq)
    print(f'detect-added-events: 履歴を足せない: {msg}', file=sys.stderr)
    return msg


def baseline_ref(since='24 hours ago'):
    """比較元のコミット参照を返す。取れなければ None。"""
    try:
        out = _git(['log', f'--since={since}', '--oneline', '--', 'events.json'])
    except Exception:                               # noqa: BLE001
        return None
    lines = [l for l in out.strip().split('\n') if l]
    if lines:
        return lines[-1].split()[0] + '~1'          # 窓の最古コミットの親
    return 'HEAD~1'                                 # 窓に何も無い = 直前と比べる


def baseline_slugs(since='24 hours ago'):
    """(比較元の slug 集合, 取れなかった理由)。取れなければ集合は None。"""
    why = ensure_history()
    ref = baseline_ref(since)
    if ref is None:
        return None, (why or 'git log が読めない')
    try:
        return {e['slug'] for e in json.loads(_git(['show', f'{ref}:events.json']))}, None
    except Exception as ex:                         # noqa: BLE001
        print(f'detect-added-events: 比較元 {ref} が取れない: {ex}', file=sys.stderr)
        return None, f'比較元 {ref} が取れない' + (f'({why})' if why else '')


def added_by_date(current, today):
    """比較元が取れない回の代用。addedDate が今日(JST)の回。"""
    return [{k: e.get(k, '') for k in FIELDS}
            for e in sorted(current, key=lambda x: x.get('slug') or '')
            if (e.get('addedDate') or '') == today and e.get('slug')]


def added(current, old_slugs):
    """current のうち old_slugs に無い回を、通知に必要な項目だけにして返す。

    old_slugs が None(比較元不明)なら空。全件を新規扱いにしない。
    """
    if old_slugs is None:
        return []
    by_slug = {e['slug']: e for e in current}
    return [{k: by_slug[s].get(k, '') for k in FIELDS}
            for s in sorted(set(by_slug) - old_slugs)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'new-events-added.json'))
    ap.add_argument('--since', default='24 hours ago')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        current = json.load(f)
    old, why = baseline_slugs(a.since)
    out = {}
    if old is None:
        evs = added_by_date(current, today_jst())
        out = {'fallback': 'addedDate', 'fallbackReason': why or ''}
        print(f'detect-added-events: 比較元が取れないので addedDate(今日)で代用: {why}',
              file=sys.stderr)
    else:
        evs = added(current, old)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(dict({'count': len(evs), 'events': evs}, **out), f, ensure_ascii=False, indent=2)
    print(f'New events added (last 24h): {len(evs)}' + (' (addedDate で代用)' if out else ''))
    return 0


def self_test():
    cur = [{'slug': 'b', 'name': 'B', 'date': '2026-10-01', 'location': '大阪'},
           {'slug': 'a', 'name': 'A', 'date': '2026-09-20', 'prefecture': '東京'}]

    r = added(cur, {'a'})
    assert [e['slug'] for e in r] == ['b'], r
    assert r[0]['name'] == 'B'
    assert r[0]['dateEnd'] == '', '欠けた項目は空文字で埋める'
    assert set(r[0]) == set(FIELDS), '通知に出す項目だけにする'

    assert added(cur, {'a', 'b'}) == [], '増分なし'
    assert [e['slug'] for e in added(cur, set())] == ['a', 'b'], 'slug順に並べる'
    assert added(cur, None) == [], '比較元不明は増分ゼロ。全件通知にしない'
    assert added([], {'a'}) == []

    ref = baseline_ref('24 hours ago')
    assert ref is None or ref.endswith('~1'), ref
    assert baseline_ref('1 second ago') == 'HEAD~1', '窓が空なら直前コミット'

    cur2 = [{'slug': 'x', 'name': 'X', 'addedDate': '2026-10-09'},
            {'slug': 'y', 'name': 'Y', 'addedDate': '2026-10-08'},
            {'slug': 'z', 'name': 'Z', 'addedDate': '2026-10-07'},
            {'slug': 'w', 'name': 'W'}]
    assert [e['slug'] for e in added_by_date(cur2, '2026-10-09')] == ['x'], \
        '代用は今日に足した回だけ。昨日の分は前日のメールに載っている。addedDate の無い回は出さない'
    assert set(added_by_date(cur2, '2026-10-09')[0]) == set(FIELDS)

    print('self-test: 11 assertions OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
