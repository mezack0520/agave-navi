#!/usr/bin/env python3
"""log-fix.py — 日次メールに出る項目を「直した」「直せなかった」記録を残す。

    python3 scripts/log-fix.py --task agave-event-update --kind coverage_gap \\
        --target "ボタの市 meets ビカク横丁 (2026-10-25)" --action listed \\
        --detail "主催 @botanoichi の告知で裏取り。new-events.json に追加"
    python3 scripts/log-fix.py --list            # 直近の記録を出す

なぜあるか(2026-09-29):
  日次メールは「他所にあって当サイトに無い」「積み残し」「異常あり」を並べる
  だけで、直すのは目崎が指示してからだった。目崎の指示は
  「報告だけでなく、そのまま直して、その結果を報告する」。
  直すのは朝のタスク(プレイブック「日次メールの項目は、報告する前に直す」)。
  **直した記録を repo に残さないと、メールは直した結果を書けない。**
  メール(build-health-mail.py)は送る回にこのファイルの未送信分を
  「今日直したもの」として出し、送った印(mailedOn)を付ける。

action:
  listed    掲載した(new-events.json に追加)
  rejected  見送りに記録した(rejected-events.json)
  fixed     データを直した(項目の修正・中止の反映・画像の採否など)
  reviewed  確認したが直すものは無かった(cancel-reviewed.json 等に記録)
  skipped   直せなかった。**--detail に理由を必ず書く**(メールに理由ごと出る)

冪等。同じ日・同じ kind・同じ target は上書きする(後の記録が勝つ)。
30日より古い記録は消す。
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(REPO, 'auto-fix-log.json')
ACTIONS = ('listed', 'rejected', 'fixed', 'reviewed', 'skipped')
KEEP_DAYS = 30


def read_fix_log():
    try:
        with open(LOG, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {'_note': '日次メールの項目を朝のタスクが直した記録。scripts/log-fix.py が書き、'
                         'build-health-mail.py が未送信分を「今日直したもの」に出して mailedOn を付ける',
                'items': []}


def write_fix_log(d):
    with open(LOG, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')


def prune(items, today):
    lim = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    return [i for i in items if (i.get('on') or '') >= lim]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task')
    ap.add_argument('--kind', help='監査の項目名など(coverage_gap / eyecatch / implausible ...)')
    ap.add_argument('--target')
    ap.add_argument('--action', choices=ACTIONS)
    ap.add_argument('--detail', default='')
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    d = read_fix_log()
    today = sitelib.today_jst()
    if a.list:
        for i in d.get('items', [])[-40:]:
            print(json.dumps(i, ensure_ascii=False))
        return 0
    if not (a.task and a.kind and a.target and a.action):
        ap.error('--task --kind --target --action が要る')
    if a.action == 'skipped' and not a.detail.strip():
        ap.error('skipped は --detail に直せなかった理由を書く')
    items = [i for i in d.get('items', [])
             if not (i.get('on') == today and i.get('kind') == a.kind and i.get('target') == a.target)]
    items.append({'on': today, 'task': a.task, 'kind': a.kind, 'target': a.target,
                  'action': a.action, 'detail': a.detail})
    d['items'] = prune(items, today)
    write_fix_log(d)
    print(f'log-fix: {a.action} {a.kind} {a.target}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
