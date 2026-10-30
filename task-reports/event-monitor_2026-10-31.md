# event-monitor 2026-10-31

- 監査: 悪化 organizer_ig_unknown_soon 0→3 / venue_key_split 0→2。data-integrity は errors 0 / warnings 0
- 直した: venue_key_split 2組(インテックス大阪・ときわミュージアムの location を施設名＋住所に揃えた)、organizerIg 2件(helisgarden / tokiwapark.official、出典頁のリンクから)
- 未対応: botanical-life-kasama-2026-11 の organizerIg(出典頁に主催のIGが無い。ブラウザ要。log-fix に skipped)
- 検査追加: organizer_ig_format(負例で1件検出、現データ0)
- 直後の venue_history_drift 4件は詳細頁が未再生成のため。daily で解消見込み
- 他の警告(アイキャッチ無し63・中止兆候6・主催IG未掲載日付7・eyecatch 10-24 抜け)は既存の継続分
