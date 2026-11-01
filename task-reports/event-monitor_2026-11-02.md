# event-monitor 2026-11-02

- audit 検出706件→709件(参考行含む)。data-integrity-check: errors 0 / warnings 0
- 悪化: venue_key_split 0→1(阪急うめだ本店 8階 GREEN AGE 系)
- 修正: urban-jungle-weeks / art-bikakushida / rare-plants-collection / hankyu-green-expo-2026 の location を「阪急うめだ本店（住所）」に統一、区画は venue(hankyu-green-expo-2026 は venue 新設)。sitelib に hankyu-umeda-honten を登録(4件でハッシュURL解消)。venue_key_split 0 / ハッシュ会場 0 を確認
- 修正直後の venue_history_drift 0→4 は daily 再生成で消える見込み
- 未対応(ブラウザ要・本タスクはブラウザ不使用): coverage_gaps 3件、organizer_unlisted_dates 8件、中止兆候3件(kusaki-biyori-bloomgarden / hanatomofesta-2026 / isij-tokyo-reikai)、再評価30日超3件
- 検査の追加: なし(今回の類型は venue_key_split が既に検出済み)
- clone 削除済み
