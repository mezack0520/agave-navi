# event-monitor 2026-11-11

- 起動記録: push済み
- audit: 検出755件。悪化は venue_slug_romaji_candidates 0→1 のみ。修正後の build-all 内の監査で 0
- data-integrity-check: errors 0 / warnings 0
- 日次メールの予定: 「タスクが直せずに残っていること」は上の1件だけ。直したので mail-request.json を push

## 直したこと
- 農マル園芸 吉備路農園: nou-marche-8th-2026-12(addedDate 11-10)で掲載3件目になり、会場頁がハッシュのままだった。
  sitelib に `_VENUE_ROMAJI_RAW`(noumaru-kibiji-noen)と `_VENUE_REDIRECTS_RAW`(v-f2260e2c)を足し、build-all で再生成。log-fix 記録済み

## 検査・書き側の拡張
- 足していない。この類型は監査(venue_slug_romaji_candidates)とプレイブック §3.2・§3.5 に既にある。
- ただし掲載3件目でのローマ字の付け忘れは 10-23・10-25・11-02・11-05・11-11 と繰り返している。載せる側(agave-event-update)が §3.2 の押す前の audit を回していない。
  次の site-health-check の週次点検で、載せる手順に audit を組み込む(例: new-events.json を書いたら merge と audit を回すスクリプト)かを判断する

## 未対応
- organizer_unlisted_dates 9件(info)、再評価待ち30日超 7件: ブラウザ要。agave-event-update の担当
- pending-judgments: プロンプト置き換え1件。今回のプロンプトは docs/task-prompts.md より前の版のままなので未解消
- スケジュール抜け: agave-event-update 2026-11-09

clone 削除済み
