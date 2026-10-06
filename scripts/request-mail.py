#!/usr/bin/env python3
"""request-mail.py — 日次メールを送る合図 mail-request.json を書く。

    python3 scripts/request-mail.py --task event-monitor
    (この後、いつもの手順で mail-request.json を push する)

なぜあるか(2026-10-06):
  日次メールは health.yml の schedule で送っていたが、GitHub の schedule は
  遅れも抜けもある。00:00 UTC 指定が 11時台、03:00 指定が 18〜19時台に走り、
  10/5・10/6 は1回も走らず、目崎に「メール来ないよ」と言われた。
  タスクの PAT は Actions 権限が無く workflow_dispatch は 403。push はできる。
  そこで朝の最後のタスク(event-monitor)が、直し終えたところでこのファイルを
  push し、health.yml(push の paths に入れてある)がメールを組んで送る。
  朝の修正がその日のメールに載る。schedule は合図が来なかった日の保険で、
  送り済みの日は送らない(build-health-mail.py の mail-state.json)。
  中身は毎回変わる時刻にする。同じ内容だとコミットにならず、合図にならない。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True)
    a = ap.parse_args()
    d = {'_note': '日次メールの合図。朝の最後のタスクが scripts/request-mail.py で書いて push し、'
                  'health.yml がメールを送る',
         'requestedAt': sitelib.now_jst().strftime('%Y-%m-%dT%H:%M:%S+09:00'),
         'task': a.task}
    with open(os.path.join(REPO, 'mail-request.json'), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f"mail-request.json を書いた({d['requestedAt']})。push するとメールが出る")
    return 0


if __name__ == '__main__':
    sys.exit(main())
