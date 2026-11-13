# event-monitor 2026-11-14

- 起動記録: push済み
- audit: 検出823件。urgent 0(前日も0)。悪化は info の rejected_revisit_stale 8→15(30日を超えた見送りが7件増えた。ブラウザ要で agave-event-update の担当)、coverage_gap_stale 3→5(今朝掲載した回で、次の巡回で消える)。metric_moved 0
- data-integrity-check: errors 0 / warnings 0
- 日次メールの予定: 「サイトに反映したこと」は朝の2件と今回の2件。「直せずに残っていること」は無し。mail-request.json を push

## 直したこと
- 朝のレポートの気づき(agavista の url が無関係の企業頁)を起点に、url / sourceUrl を持つ全回の非IGの出典137件を取得し、sitelib の page_is_wrong_edition / page_is_wrong_place と名称の出現で洗った
- agavista-vol2-matsuyama-2026-06: url が化学メーカーの報道発表一覧(jpn.sika.com)。催し名も愛媛も無い。url を外した
- green-breeze-fes-vol3: url が福井の音楽フェス GREEN FLASH FES の公式。url を外した(出典は主催の IG が残る)
- どちらも enrich の関門(2026-09-10〜12)より前の 2026-04 の取り込み。今の enrich は同じ頁を wrong_place で弾く。書き戻しは開催前の回だけなので戻らない
- 他の当たりは、過去の回の出典が主催のトップ・一覧で次の回に入れ替わったもので、誤りではない
- log-fix: 上の2件 fixed、botanical-life-kasama-2026-11 の organizer_ig_unknown_soon(10-31 に skipped)は organizerIg 入り・終了済みで reviewed

## 検査の拡張
- `source_page_wrong_place`(info): 出典の頁が別の県だけを名乗っているか。日付を散文で書かない別サイトは source_page_wrong_edition を素通りするので足した
- 判定材料は check-cancelled.py の analyze が cancel-watch.json に書く wrongPlace / pagePrefs(sitelib.page_is_wrong_place と同じ規則)。自己テストに3件足し、通過
- 修正前の2件の実頁に当てて2件とも True。今の cancel-watch.json(17件)はまだキーを持たないので0件で、明日の daily から効く。注入した記録で監査に1件出ることを確かめた

## 未対応
- organizer_unlisted_dates 7件(info)、再評価待ち30日超 15件: ブラウザ要。agave-event-update の担当
- task_run_gap: agave-event-update 2026-11-09(過去の日で直す先は無い)
