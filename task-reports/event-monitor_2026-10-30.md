# event-monitor 2026-10-30

- audit: 悪化 desc_date_mismatch 0→3 / duplicate_indexable_title 0→1。原因は本日追加の2日開催(Bizarre Plants Fair 11/1・11/8)と阪急うめだ回の説明文。
- 修正(events.json): Bizarre Plants Fair の name を (11/1)(11/8) に書き分け、説明文を前回・次回表記に。art-bikakushida-hankyu-umeda-2026-11 の説明文に「同時開催」を付与。desc_date_mismatch は 0。duplicate title は次の daily で頁が再生成されて解消。
- audit 拡張: same_name_upcoming(同名の開催予定が複数)を追加。頁生成前の events.json 段階で検出する。
- data-integrity-check: errors 0 / warnings 0。
- 未解消: eyecatch の 10-24 実行抜け(過去日・対処なし)、見送り2件が30日超(再評価待ち)。pending-judgments は空。
- clone 削除済み。
