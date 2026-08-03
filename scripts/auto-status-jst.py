#!/usr/bin/env python3
"""auto-status-jst.py — upcoming → past を JST 基準で確定させる。

build-all.sh の先頭で走る。ページ生成より前に events.json の status を正しくしないと、
ランディング頁・フィード・sitemap が終了済みを「開催予定」として出力してしまう。

なぜ workflow ではなくここに置くか:
daily.yml の Auto status update ステップは date.today() を使っている。
GitHub Actions ランナーは UTC なので、06:00 JST(=前日 21:00 UTC)起動時の
ランナー日付は前日になり、「JSTで昨日終了」のイベントが past にならない。
結果、終了翌日の丸一日ぶん、30頁前後のランディングで終了済みが開催予定として並んでいた
(2026-08-03 の週次点検で13件検出)。
ワークフローファイルの修正には PAT の workflow スコープが要り、
運用中の PAT は contents 権限のみで push できない。
build-all.sh は全ワークフロー共通の単一情報源なので、ここに置けば
daily / sync-events / weekly-enrichment のどの経路から入っても同じ不変条件が保たれる。

冪等。変更が無ければ events.json に触らない。
"""
import json
import os
import sys
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from sitelib import today_jst

EVENTS = os.path.join(REPO, 'events.json')


def main():
    today = date.fromisoformat(today_jst())
    with open(EVENTS, encoding='utf-8') as f:
        events = json.load(f)

    changed = []
    for e in events:
        d = e.get('dateEnd') or e.get('date')
        if not d or e.get('status') != 'upcoming':
            continue
        try:
            if date.fromisoformat(d) < today:
                e['status'] = 'past'
                changed.append(e.get('slug'))
        except ValueError:
            continue

    if changed:
        with open(EVENTS, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)
        print(f"auto-status-jst: {len(changed)}件を past に変更 (JST {today})")
        for s in changed:
            print(f"  - {s}")
    else:
        print(f"auto-status-jst: 変更なし (JST {today})")


if __name__ == '__main__':
    main()
