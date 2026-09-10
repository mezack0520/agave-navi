#!/usr/bin/env python3
"""detect-new-slugs.py — 直前のコミットと比べて増えた slug を出す。

**2026-09-10 に sync-events.yml から出した。**取り込み直後の
「どれが新規か」を workflow の中で計算していて、ローカルで確かめられなかった。

出力: `slugs=a,b,c`（GITHUB_OUTPUT にそのまま追記できる形）
比較元は `git show HEAD:events.json`。取り込みのコミット前に呼ぶ前提。
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def new_slugs(events_path, ref='HEAD:events.json'):
    try:
        prev = subprocess.run(['git', 'show', ref], cwd=REPO,
                              capture_output=True, text=True).stdout
        prev_slugs = {e.get('slug') for e in json.loads(prev)}
    except Exception:                               # noqa: BLE001
        # 比較元が取れない回は「全部が新規」ではなく「不明」。
        # 空集合にすると全件を新規として enrich に流してしまう
        return None
    with open(events_path, encoding='utf-8') as f:
        cur = json.load(f)
    return sorted({e['slug'] for e in cur if e.get('slug') not in prev_slugs})


def main():
    p = os.path.join(REPO, 'events.json')
    s = new_slugs(p)
    if s is None:
        print('slugs=')
        print('detect-new-slugs: 比較元が取れなかった。空で返す', file=sys.stderr)
        return 0
    print('slugs=' + ','.join(s))
    return 0


if __name__ == '__main__':
    sys.exit(main())
