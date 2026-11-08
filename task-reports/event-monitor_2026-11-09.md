# event-monitor 2026-11-09

## 監査
- audit: 検出730件。悪化 rejected_revisit_expired 0→1、解消 cancel_review_repeated。data-integrity-check: errors 0 / warnings 0。
- 日次メールの予定: 「タスクが直せずに残っていること」1件のみ。

## 直したこと
- nihonosato-taniku-hanbaikai-2026-11-08: 開催日(11/8)を過ぎたため revisit=false、理由に一文追記(rejected-events.json)。log-fix fixed。

## 未対応(ブラウザ要。このタスクはブラウザを使わないため needs_browser で skipped 記録)
- coverage_gaps 2件: 日本サボテン狂人会 交換会(11/15)、ハッピーグリーンDays(12/20)
- organizer_unlisted_dates 5件: @greenfarmkanazawa、@plants2306.fe、@vandaka_plants、@wakayama_cactus_club、@yamada_ishigaki(珍奇植物マーケット in 八重山 vol.2 11/20)

## 監査の拡張
- 今回は追加なし。新しい類型は観測されず(悪化の1件は既存の rejected_revisit_expired が検出済み。保留の再評価が開催前日だったため当日の対応が間に合わなかった)。
- 追加の不変条件を手元で走査(end<start、日付書式、rescheduled の previousStartDate 欠け、alias 重複など): 該当なし。

## 後始末
- mail-request.json を push(日次メール)。clone 削除済み。
