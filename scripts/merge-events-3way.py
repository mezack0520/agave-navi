#!/usr/bin/env python3
"""merge-events-3way.py — events.json を回(slug)と項目の単位で3方向マージする。

    python3 scripts/merge-events-3way.py BASE OURS THEIRS OUT
    python3 scripts/merge-events-3way.py --self-test

なぜ要るか(2026-09-28):
  events.json と new-events.json を1つの push に入れると、daily(events.json の
  push で起動)と sync-events(new-events.json の push で起動)が同時に走り、
  両方が events.json を書く。ci-push.sh は後から push する側の差分を
  `git apply --3way` で相手の版に貼り直すが、**テキストの差分は隣り合う行を
  触っただけで衝突する。**sync-events #111 は daily が回の status を書き換えた
  行のそばに新規5件を足して衝突し、取り込みが落ちた(新規5件が載らず
  new-events.json が公開URLに残った)。
  JSON としては「別の回」「同じ回の別の項目」を触っているだけなので、
  項目の単位で見れば衝突していない。

規則:
  - 両方が同じ回の同じ項目を別の値にしたときだけ本当の衝突。OURS(この
    ジョブ)を採って標準エラーに出す。落とすより、後の監査で見えるほうがよい
  - 片方だけが変えた項目はその値を採る。項目の削除も変更として扱う
  - OURS だけにある回は末尾に足す。THEIRS だけにある回はそのまま残す
  - 片方が消した回は、もう片方がその回を変えていなければ消す
  - 並びと書式は THEIRS に合わせる(indent=2、末尾改行は THEIRS のまま)
"""
import json
import sys

_MISSING = object()


def _load(p):
    with open(p, encoding='utf-8') as f:
        raw = f.read()
    return json.loads(raw), raw


def merge(base, ours, theirs):
    """(merged, conflicts)。conflicts は 'slug.field' の一覧"""
    b = {e.get('slug'): e for e in base}
    o = {e.get('slug'): e for e in ours}
    t = {e.get('slug'): e for e in theirs}
    conflicts = []
    out = []
    for ev in theirs:
        sl = ev.get('slug')
        be, oe = b.get(sl), o.get(sl)
        if oe is None:
            # OURS に無い。OURS が消したのか(BASE にある)、THEIRS が足したのか
            if be is not None and ev == be:
                continue  # OURS が消し、THEIRS は触っていない → 消す
            out.append(ev)
            continue
        if be is None:
            be = {}
        m = {}
        keys = list(ev.keys()) + [k for k in oe.keys() if k not in ev] \
            + [k for k in be.keys() if k not in ev and k not in oe]
        for k in keys:
            bv, ov, tv = be.get(k, _MISSING), oe.get(k, _MISSING), ev.get(k, _MISSING)
            if ov == bv:
                v = tv
            elif tv == bv or ov == tv:
                v = ov
            else:
                v = ov
                conflicts.append(f'{sl}.{k}')
            if v is not _MISSING:
                m[k] = v
        out.append(m)
    for ev in ours:
        sl = ev.get('slug')
        if sl in t:
            continue
        be = b.get(sl)
        if be is None:
            out.append(ev)          # OURS が足した回
        elif ev != be:
            out.append(ev)          # THEIRS が消したが OURS が変えている → 残す
            conflicts.append(f'{sl}(THEIRS が削除)')
        # else: THEIRS が消し、OURS は触っていない → 消す
    return out, conflicts


def main(argv):
    if argv[1:2] == ['--self-test']:
        return self_test()
    if len(argv) != 5:
        print(__doc__)
        return 2
    base, _ = _load(argv[1])
    ours, _ = _load(argv[2])
    theirs, traw = _load(argv[3])
    merged, conflicts = merge(base, ours, theirs)
    txt = json.dumps(merged, ensure_ascii=False, indent=2)
    with open(argv[4], 'w', encoding='utf-8') as f:
        f.write(txt + ('\n' if traw.endswith('\n') else ''))
    for c in conflicts:
        print(f'::warning::events.json の同じ項目を両方が変えた。こちらの値を採った: {c}',
              file=sys.stderr)
    print(f'events.json を項目単位でマージした(衝突 {len(conflicts)} 件)')
    return 0


def self_test():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print(f'NG {label}: {got!r} != {want!r}')

    base = [{'slug': 'a', 'status': 'upcoming', 'name': 'A'},
            {'slug': 'b', 'status': 'upcoming'}]
    # daily が a の status を変え、sync が c を足した(#111 の形)
    theirs = [{'slug': 'a', 'status': 'past', 'name': 'A'}, {'slug': 'b', 'status': 'upcoming'}]
    ours = base + [{'slug': 'c', 'status': 'upcoming'}]
    m, c = merge(base, ours, theirs)
    chk('別の回', [(e['slug'], e['status']) for e in m],
        [('a', 'past'), ('b', 'upcoming'), ('c', 'upcoming')])
    chk('別の回 衝突なし', c, [])
    # 同じ回の別の項目
    ours = [{'slug': 'a', 'status': 'upcoming', 'name': 'A2'}, base[1]]
    m, c = merge(base, ours, theirs)
    chk('同じ回の別項目', m[0], {'slug': 'a', 'status': 'past', 'name': 'A2'})
    # 項目の削除
    ours = [{'slug': 'a', 'status': 'upcoming'}, base[1]]
    m, c = merge(base, ours, theirs)
    chk('削除も変更', m[0], {'slug': 'a', 'status': 'past'})
    # 本当の衝突は OURS
    ours = [{'slug': 'a', 'status': 'cancelled', 'name': 'A'}, base[1]]
    m, c = merge(base, ours, theirs)
    chk('衝突は OURS', (m[0]['status'], c), ('cancelled', ['a.status']))
    # 片方が消した回
    ours = [base[0]]
    m, c = merge(base, ours, theirs)
    chk('OURS が消した(THEIRS 未変更)', [e['slug'] for e in m], ['a'])
    theirs2 = [base[0]]
    ours2 = [base[0], {'slug': 'b', 'status': 'past'}]
    m, c = merge(base, ours2, theirs2)
    chk('THEIRS が消したが OURS が変えた', [e['slug'] for e in m], ['a', 'b'])
    print('self-test OK' if ok else 'self-test NG')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
