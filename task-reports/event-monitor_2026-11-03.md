# event-monitor 2026-11-03

- audit.py: 検出720件、urgent 0。data-integrity-check: errors 0 / warnings 0。
- cancel_suspects 5件(前日3件)を一次情報で確認。すべて開催予定のまま。cancel-reviewed.json に記録。
- isij-tokyo-reikai-2026-12-20 は2024年の中止告知が頁に残る誤検知。check-cancelled.py に drop_past_notice と自己テストを追加し、audit.py から自己テストを呼ぶ。実頁で強い語の検出が消えることを確認。
- 未処理(判断が要る・機械で確定できない): coverage_gaps 3件、organizer_unlisted_dates 8件、再評価待ちの見送り3件(30日超)。pending-judgments.json は0件のまま。
- clone 削除済み。
