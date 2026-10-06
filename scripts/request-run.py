#!/usr/bin/env python3
"""request-run.py — GitHub の処理を起こす合図ファイルを書く。書いた後に push する。

    python3 scripts/request-run.py crawl --task event-listing-review   # 朝の巡回(daily.yml)
    python3 scripts/request-run.py mail  --task event-monitor          # 日次メール(health.yml)

合図ファイル:
  crawl-request.json  daily.yml が push で拾い、日付照合・未掲載の巡回・中止の見張り・
                      主催IGの見張り(アイキャッチ候補もここで作る)を回す
  mail-request.json   health.yml が push で拾い、全チェックを回して日次メールを送る

なぜあるか(2026-10-06):
  GitHub の schedule は時刻を当てにできない。daily の 06:00 指定は 08:50〜10:40 に、
  health の 00:00 指定は 11時台、03:00 指定は 18〜19時台に走り、health は 10/5・10/6 に
  1回も走らず「メール来ないよ」と言われた。時刻どおりに動くのは PC の朝のタスクだけなので、
  **朝の流れはタスクが合図を push して進める。**schedule は合図が来なかった日の保険。
  タスクの PAT は Actions 権限が無く workflow_dispatch は 403。push はできる。
  中身は毎回変わる時刻にする。同じ内容だとコミットにならず、合図にならない。
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = {
    'crawl': ('crawl-request.json', '朝の巡回の合図。最初の朝のタスクが書いて push し、daily.yml が巡回する'),
    'mail': ('mail-request.json', '日次メールの合図。朝の最後のタスクが書いて push し、health.yml がメールを送る'),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('kind', choices=sorted(KINDS))
    ap.add_argument('--task', required=True)
    a = ap.parse_args()
    fname, note = KINDS[a.kind]
    d = {'_note': note + '(scripts/request-run.py)',
         'requestedAt': sitelib.now_jst().strftime('%Y-%m-%dT%H:%M:%S+09:00'),
         'task': a.task}
    with open(os.path.join(REPO, fname), 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print(f"{fname} を書いた({d['requestedAt']})。push すると動く")
    return 0


if __name__ == '__main__':
    sys.exit(main())
