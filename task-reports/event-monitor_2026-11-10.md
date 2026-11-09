# event-monitor 2026-11-10

- 起動記録: push済み
- audit: 検出742件。悪化は region_mismatch 0→1 のみ
- data-integrity-check: errors 0 / warnings 1 → 修正後 0

## 直したこと
- chinki-shokubutsu-market-yaeyama-vol2-2026-11 の region を 沖縄 → 九州(sitelib.PREF_TO_REGION の定義どおり)。events.json 直接編集。生成物は daily が再生成する

## 検査・書き側の拡張
- 原因は new-events.json の手書き region が取り込みで検証されないこと。監査(region_mismatch)は既にあったため、書き側を直した
- scripts/merge-new-events.py: 新規・更新とも region を prefecture から決め直す。self-test 追加

## 未対応
- 他所掲載で未掲載の候補 6件、主催投稿の未掲載日付 5件、再評価待ち30日超 5件: 今回は確認していない(agave-event-update の担当表どおり翌朝以降)
- スケジュール抜け: agave-event-update が 2026-11-09 に未実行

clone 削除済み
