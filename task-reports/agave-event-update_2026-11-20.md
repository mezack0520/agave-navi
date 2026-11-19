# agave-event-update 2026-11-20

## 掲載(new-events.json 3件、sync-events で取り込み済み)
- 多肉楽市 in 高鍋 11/22 … 保留から掲載。主催 @medelu04 の固定投稿 Ddumu0yHDeZ(チラシに日時・会場・主催「多肉楽市実行委員会」)。見張っていた @succulent_room_m は販売用の別アカウントだった
- GREEN GATHER vol.3 12/20 … 主催 @dining_bar_yoi Df6JU-eJyxm(Google 検索から)
- 第2回 TANIKU JAM in京都 2027-01-09 … 保留(revisit_stale)から掲載。主催 @tanikujam DetweShPe9J、時刻は協力 @irodoleaf.taniku の告知

## 既存の回の修正(events.json)
- gamagori-taniku-festa-hamamatsu-2nd-2027-01: 主催告知 Df65ESmyLxu で time 10:00〜15:00、出典・説明文を差し替え(日次メールの time_vs_organizer_post)

## 見送り・保留の更新(rejected-events.json)
- 削除: hinata-tanikuen-event-miyazaki-2026-11、taniku-jam-kyoto-2027-01(掲載したため)
- revisit_stale 残り: monster-plants-kagawa-2027-03 は今回見ていない

## Step0
- coverage-gaps: errors 0、gaps 0。truncatedUnresolved 5件は既存・見送りに当たり済み
- scan-organizer-posts 160行を読んだ。未掲載の新規なし(森の多肉園BIG、多肉だょ津山/福山、ガーデンプラザ華、麋祭 vol.02 などは掲載済み)
- Google(qdr:w2)6本で結果、7本目以降は `a h3` 0件で打ち切り。中止・延期の検索と search-demand 2件(アガベミーティング 2027、天下一植物界 2027)は未実施
- LEAFLA 連番 7108〜7135 を確認。右端 7111(増えず)
- watch-sources 巡回: 平日のため対象外

## 日次メール項目
- time_vs_organizer_post 1件: fixed(上記)
- needs_browser の積み残し: 0件

## 気づき
- 保留中の主催 handle が販売用アカウントだった例。プレイブック §3.3 に1行追記

clone 削除済み
