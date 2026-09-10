#!/usr/bin/env python3
"""detect-added-events.py — 直近24時間で増えた回を new-events-added.json に書く。

**2026-09-10 に health.yml から出した。**24時間ぶんの差分計算を YAML に
直書きしていたので、ローカルで確かめられず、比較元が取れない回に
どう振る舞うのかもコードを読まないと分からなかった。

比較元は「24時間以内に events.json を触った最古のコミットの親」。
その窓に何も無ければ `HEAD~1`。どちらも取れない回は **増分ゼロ** にする
(全件を新規として通知に流すより、黙って落とすほうが安全)。

  python3 scripts/detect-added-events.py [--out new-events-added.json]
  python3 scripts/detect-added-events.py --self-test
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIELDS = ('slug', 'name', 'date', 'dateEnd', 'location', 'prefecture')


def _git(args):
    return subprocess.check_output(['git'] + args, cwd=REPO,
                                   stderr=subprocess.DEVNULL).decode()


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
    """比較元の slug 集合。取れなければ None(= 増分ゼロ扱い)。"""
    ref = baseline_ref(since)
    if ref is None:
        return None
    try:
        return {e['slug'] for e in json.loads(_git(['show', f'{ref}:events.json']))}
    except Exception as ex:                         # noqa: BLE001
        print(f'detect-added-events: 比較元 {ref} が取れない: {ex}', file=sys.stderr)
        return None


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
    evs = added(current, baseline_slugs(a.since))
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump({'count': len(evs), 'events': evs}, f, ensure_ascii=False, indent=2)
    print(f'New events added (last 24h): {len(evs)}')
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

    print('self-test: 9 assertions OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
