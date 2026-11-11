# event-monitor 2026-11-12

- 起動記録: push済み
- audit: 検出775件。urgent 0、前回からの悪化・解消なし
- data-integrity-check: errors 0 / warnings 0
- 日次メールの予定: 「サイトに反映したこと」1件(朝の check-cancelled.py の修正)と今回の1件。「直せずに残っていること」は無し。mail-request.json を push

## 直したこと
- ojisans6-kato-engei-2026-11: 説明文「2026年11月8日(土)」→(日)。主催の告知 Delr1AjyRIO は「11/8(日)」で、日付は正しく曜日が誤り。log-fix 記録済み

## 検査の拡張
- `weekday_mismatch`(urgent): 説明文と time の曜日付きの日付(「11/8(土)」「11月8日(土)」「22日(日)」)を暦と突き合わせる。
  規則は sitelib.event_weekday_mismatches。年の無い月日は開催日に最も近い年、月の無い日は会期の中の日として読む。
  修正前のデータで1件(上記)、10-25 版で1件(同じ回)、10-01・09-01・08-01 版で0件。誤検知0
- プレイブックの「何をどう直すか」の表に1行足した

## 見たが足さなかったもの
- location に区画(展示室・小ホールなど)まで書いた回が89件ある。venue_key_split は割れが起きてから鳴る。件数が多く大半は他の回と割れていないので、今回は検査にしない

## 未対応
- organizer_unlisted_dates 7件(info)、再評価待ち30日超 8件: ブラウザ要。agave-event-update の担当
- task_run_gap: agave-event-update 2026-11-09。レポートもコミットも無く、その日はタスクが止まっていた(過去の日で直す先は無い)

clone 削除済み
