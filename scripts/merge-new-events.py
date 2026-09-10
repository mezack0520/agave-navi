#!/usr/bin/env python3
"""merge-new-events.py — new-events.json を events.json に取り込む。

**2026-09-10 に sync-events.yml から出した。**取り込みの規則が
workflow の `run: |` に直書きされていて、ローカルで実行も検証もできなかった。
2026-08-31 にカード挿入の処理が同じ形で埋まっていて、手で足した回は
カードが作られず、監査の案内どおりにやっても直らない状態を作っている。
**CIでしか走らないコードは壊れても分からない。**

取り込みの規則。

- slug が無ければ追加する
- slug が既にあれば、**値のあるキーだけ**上書きする。空で潰さない
- 並びは 開催予定を先、その中は日付昇順

Usage:
  python3 scripts/merge-new-events.py [--in new-events.json]
  python3 scripts/merge-new-events.py --dry-run     # 書かずに結果だけ出す
  python3 scripts/merge-new-events.py --self-test   # 判定だけ検証(ファイル不要)
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def merge(events, new_events):
    """(結果, 追加したslug, 更新したslug)。**この関数が取り込みの規則。**"""
    existing = {e.get('slug') for e in events}
    added, updated = [], []
    for ne in new_events:
        slug = ne.get('slug')
        if slug not in existing:
            events.append(ne)
            existing.add(slug)
            added.append(slug)
            continue
        for e in events:
            if e.get('slug') != slug:
                continue
            for k, v in ne.items():
                # 空で既存を潰さない。取り込み側が持っていない項目は触らない
                if v and v != e.get(k):
                    e[k] = v
                    if slug not in updated:
                        updated.append(slug)
            break
    events.sort(key=lambda e: (0 if e.get('status') == 'upcoming' else 1,
                               e.get('date', '')))
    return events, added, updated


def self_test():
    bad = 0

    def chk(label, got, want):
        nonlocal bad
        ok = got == want
        if not ok:
            bad += 1
        print(f'  {"OK " if ok else "NG "} {label}: {got!r} 期待={want!r}')

    ev = [{'slug': 'a', 'name': 'A', 'date': '2026-10-01', 'status': 'upcoming'}]
    out, add, upd = merge([dict(x) for x in ev],
                          [{'slug': 'b', 'name': 'B', 'date': '2026-09-01',
                            'status': 'upcoming'}])
    chk('新規は追加される', add, ['b'])
    chk('開催予定は日付順', [e['slug'] for e in out], ['b', 'a'])

    out, add, upd = merge([dict(x) for x in ev], [{'slug': 'a', 'name': ''}])
    chk('空では上書きしない', out[0]['name'], 'A')
    chk('空だけなら更新扱いにしない', upd, [])

    out, add, upd = merge([dict(x) for x in ev],
                          [{'slug': 'a', 'time': '10:00〜16:00'}])
    chk('値があれば足す', out[0].get('time'), '10:00〜16:00')
    chk('更新として数える', upd, ['a'])

    out, _a, _u = merge([{'slug': 'p', 'date': '2026-01-01', 'status': 'past'},
                         {'slug': 'u', 'date': '2026-12-01', 'status': 'upcoming'}],
                        [])
    chk('終了は後ろ', [e['slug'] for e in out], ['u', 'p'])
    print('\n結果:', 'すべて通過' if not bad else f'{bad}件 失敗')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='new-events.json')
    ap.add_argument('--events', default='events.json')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    inp = args.inp if os.path.isabs(args.inp) else os.path.join(REPO, args.inp)
    evp = args.events if os.path.isabs(args.events) else os.path.join(REPO, args.events)
    if not os.path.exists(inp):
        print('No new-events.json found. Skipping merge.')
        return 0
    with open(evp, encoding='utf-8') as f:
        events = json.load(f)
    with open(inp, encoding='utf-8') as f:
        new_events = json.load(f)

    events, added, updated = merge(events, new_events)
    if not args.dry_run:
        with open(evp, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

    up = sum(1 for e in events if e.get('status') == 'upcoming')
    print(f'Total: {len(events)}, Upcoming: {up}')
    if added:
        print(f'Added {len(added)}: {", ".join(added)}')
    if updated:
        print(f'Updated {len(updated)}: {", ".join(updated)}')
    if not added and not updated:
        print('No changes.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
