#!/usr/bin/env python3
"""check-inquiry-handoff.py — 問い合わせ受け渡し箱が読める状態かを見る。

**2026-09-10 に notify-inquiry.yml から出した。**「どう壊れていたら鳴るのか」が
YAML の中にしか無く、鳴らしてみるまで確かめられなかった。

new-inquiries.json が JSON として読めなくなると event-listing-review が
受け渡し箱を読めず、問い合わせが黙って滞留する。それだけを判定する。
通知メールそのものは GAS 側が出す(理由は notify-inquiry.yml の冒頭)。

出力: `broken=true|false` と `reason=` (GITHUB_OUTPUT にそのまま追記できる形)

  python3 scripts/check-inquiry-handoff.py
  python3 scripts/check-inquiry-handoff.py --self-test
"""
import argparse
import json
import os
import pathlib
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def broken_reason(raw):
    """壊れている理由を返す。読めるなら空文字。raw が None は「ファイルが無い」。"""
    if raw is None:
        return 'new-inquiries.json が存在しません'
    try:
        d = json.loads(raw)
    except Exception as e:                          # noqa: BLE001
        return f'JSONとして読めません: {e}'
    if not isinstance(d, dict):
        return 'トップレベルがオブジェクトではありません'
    if not isinstance(d.get('items', []), list):
        return 'items が配列ではありません'
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default=os.path.join(REPO, 'new-inquiries.json'))
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    p = pathlib.Path(a.inp)
    reason = broken_reason(p.read_text(encoding='utf-8') if p.exists() else None)
    print('broken=' + ('true' if reason else 'false'))
    print('reason=' + reason.replace('\n', ' '))
    return 0


def self_test():
    assert broken_reason('{"items": []}') == '', '空の箱は壊れていない'
    assert broken_reason('{"items": [{"type": "掲載"}]}') == ''
    assert broken_reason('{}') == '', 'items が無いだけなら壊れていない(従来動作)'
    assert broken_reason(None).endswith('存在しません')
    assert broken_reason('{壊れ').startswith('JSONとして読めません')
    assert broken_reason('{"items": {}}') == 'items が配列ではありません'
    assert broken_reason('[]') == 'トップレベルがオブジェクトではありません'
    assert '\n' not in broken_reason('{"items": 1}')
    # 実物が読めること
    p = pathlib.Path(REPO) / 'new-inquiries.json'
    if p.exists():
        assert broken_reason(p.read_text(encoding='utf-8')) == '', '実物が壊れている'
    print('self-test: 9 assertions OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
