# agave-event-update 2026-11-16 (月)

## Step0 カバレッジ
- coverage-gaps 1件(errors 0): 群馬第4交換会 11月場所(11/22)。既存の見送り gunma-dai4-koukankai-2026-09(closedGatherings、毎月開催)と同じ催しなのに日付の幅で外れていた。見送り記録に `seriesWide: true` を付け、coverage-sweep.py がこの印の記録を日付で絞らず当てるようにした(プレイブック §3.3 に1行)。
- scan-organizer-posts 139行を通読。見送り: @bears_palm の多肉園おひさまのワークショップ 11/21・12/6(workshopOnly)、東海フラワーショウ2027 1/23-24(@okibota_2021 の紹介、outOfScopeGenres)。ほかの植物系の行は掲載済みか見送り済み。
- 未特定: @kotetu_plants の予定「11/29(日) 多肉まつり」は名前だけで主催・会場が分からず、記録せず。
- LEAFLA 連番 7108〜7140 を確認。右端 7111(増えず)。
- Google 検索は最初の fetch から `a h3` 0件で打ち切り(4日続き)。WebSearch 3本(多肉楽市 高鍋 / 多肉まつり 11/29 / 中止・延期)は該当なし。
- watch-sources 巡回は日曜のみ(本日は月曜 JST)。

## 日次メールの項目
- time_vs_organizer_post 1件: 第2回 ゆるっと多肉マルシェ(12/27)に time 10:00〜15:00、url/sourceUrl を主催の告知 DfvxHS9n7ff に、説明文を出店者紹介(7店・WS)に合わせた。
- 保留の再評価: ヒナタ多肉園(11/22)は名称「多肉楽市 in高鍋」と判明(@the_factory_otto Dfwpw0yk3-1)したが主催 @succulent_room_m に告知なし。unverified 継続、alias に多肉楽市。
- 本業後の build-health-mail 予定: 生成物の古さ(index_card_body_drift、daily の再生成で消える)のみ。

## 反映
- push 3回(記録 / events.json / 見送りとコード)。new-events.json の追加なし。

clone 削除済み。
