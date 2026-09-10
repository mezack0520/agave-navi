#!/usr/bin/env python3
"""apply-ops.py — ops ペイロードを repo に適用する。

**2026-09-10 に ops.yml から出した。**58行が workflow の `run: |` に
直書きされていて、ローカルで実行も検証もできなかった。
とくに write-file / delete-file の**書き込み先の制限**が、
テストの当てられない場所に置かれていた。

出したときに穴が1つ見つかった。制限は
`p.startswith(('/', '.github/')) or '..' in p` だったので、
**`./.github/workflows/x.yml` が素通りする。**`.github/` で始まらず
`..` も含まないため。正規化してから見る形に直した。

ops は workflow_dispatch の inputs か repository_dispatch の
client_payload から来る。どちらも repo への書き込み権限が要るので
これは境界ではなく多重の歯止めだが、歯止めが効いていないのは別の話。

Usage:
  python3 scripts/apply-ops.py                 # 環境変数 OPS_WD / OPS_RD から
  python3 scripts/apply-ops.py --ops '<json>'
  python3 scripts/apply-ops.py --self-test
"""
import argparse
import json
import os
import posixpath
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 書き込み・削除を許さない場所。**正規化してから当てる。**
FORBIDDEN_PREFIXES = ('.github/', '.git/')


def path_allowed(p):
    """repo 相対で、禁止された場所を指していなければ True。"""
    if not p or not isinstance(p, str):
        return False
    if p.startswith('/') or (len(p) > 1 and p[1] == ':'):
        return False                      # 絶対パス(Windows のドライブ含む)
    norm = posixpath.normpath(p.replace('\\', '/'))
    if norm.startswith('../') or norm == '..':
        return False                      # repo の外へ出る
    return not any(norm == d.rstrip('/') or norm.startswith(d)
                   for d in FORBIDDEN_PREFIXES)


def _load(p):
    with open(os.path.join(REPO, p), encoding='utf-8') as f:
        return json.load(f)


def _dump(p, data, indent):
    with open(os.path.join(REPO, p), 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def apply_ops(ops):
    """(events を書き換えたか, ログ行)。例外ではなく SystemExit で落とす。"""
    if isinstance(ops, dict):
        ops = [ops]
    events_changed = False
    log = []
    for o in ops:
        op = o.get('op')
        if op == 'set-field':
            events = _load('events.json')
            hit = [e for e in events if e.get('slug') == o['slug']]
            if not hit:
                print(f"::error::slug not found: {o['slug']}")
                sys.exit(1)
            hit[0][o['field']] = o['value']
            _dump('events.json', events, 2)
            events_changed = True
            log.append(f"set-field: {o['slug']}.{o['field']} = {o['value']}")
        elif op in ('write-file', 'delete-file'):
            p = o.get('path', '')
            if not path_allowed(p):
                print(f'::error::path not allowed: {p}')
                sys.exit(1)
            full = os.path.join(REPO, p)
            if op == 'write-file':
                d = os.path.dirname(full)
                if d:
                    os.makedirs(d, exist_ok=True)
                with open(full, 'w', encoding='utf-8') as f:
                    f.write(o.get('content', ''))
                log.append(f"write-file: {p} ({len(o.get('content', ''))} bytes)")
            elif os.path.exists(full):
                os.remove(full)
                log.append(f'delete-file: {p}')
            else:
                log.append(f'delete-file: {p} (not found, skip)')
        elif op == 'queue-remove':
            q = _load('pending-judgments.json')
            before = len(q['items'])
            q['items'] = [i for i in q['items'] if i.get('id') != o['id']]
            _dump('pending-judgments.json', q, 1)
            log.append(f"queue-remove: {o['id']} ({before} -> {len(q['items'])})")
        else:
            print(f'::error::unknown op: {op}')
            sys.exit(1)
    return events_changed, log


def self_test():
    bad = 0

    def chk(label, got, want):
        nonlocal bad
        ok = got == want
        if not ok:
            bad += 1
        print(f'  {"OK " if ok else "NG "} {label}: {got!r} 期待={want!r}')

    chk('普通のパス', path_allowed('events.json'), True)
    chk('下の階層', path_allowed('images/events/a.jpg'), True)
    chk('絶対パス', path_allowed('/etc/passwd'), False)
    chk('Windowsの絶対パス', path_allowed('C:/x'), False)
    chk('.github 直', path_allowed('.github/workflows/daily.yml'), False)
    # 直書きだった頃に素通りしていた形
    chk('./.github', path_allowed('./.github/workflows/daily.yml'), False)
    chk('遠回りの .github', path_allowed('a/../.github/x.yml'), False)
    chk('.git 配下', path_allowed('.git/config'), False)
    chk('repo の外', path_allowed('../x'), False)
    chk('空', path_allowed(''), False)
    print('\n結果:', 'すべて通過' if not bad else f'{bad}件 失敗')
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ops')
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    raw = (args.ops or os.environ.get('OPS_WD') or '').strip()
    if not raw or raw == 'null':
        raw = (os.environ.get('OPS_RD') or '').strip()
    if not raw or raw == 'null':
        print('::error::no ops payload')
        return 1
    events_changed, log = apply_ops(json.loads(raw))
    for line in log:
        print(line)
    out = os.environ.get('GITHUB_OUTPUT')
    val = '1' if events_changed else '0'
    if out:
        with open(out, 'a') as f:
            f.write(f'events_changed={val}\n')
    else:
        print(f'(events_changed={val})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
