# event-monitor 2026-11-01

- 起動記録: task-runs.json を push 済み
- audit.py: 検出 781件。悪化 region_mismatch 0→1
- data-integrity-check.py: errors 0 / warnings 1(同件)
- 修正: vabudo-3sha-popup-shizuoka-2026-11 の region 中部→東海(events.json 直接編集)
- 修正直後の audit の悪化 index_card_attr_drift / feed_slug_drift / landing_event_set_drift は daily 再生成待ちの一時的なもの
- 監査の追加: なし。region_mismatch が既に検出済みで新しい類型なし
- 未処理: 他所に出ていて当サイトに無い候補4件・中止兆候6件・主催者投稿の先日付11件は agave-event-update の担当範囲で今回は触れず
- clone 削除済み
