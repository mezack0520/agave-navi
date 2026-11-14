# agave-event-update 2026-11-15 (日)

## Step0 カバレッジ
- coverage-gaps 0件(errors 0)。truncatedUnresolved の「奈良県三宅町のThe PlantsでChris...」は LEAFLA topics7023 の Christmas Wreath Workshop(@theplants_hanamasa)。workshopOnly で見送り記録。
- scan-organizer-posts 178行を通読。見送り: ゆくはし植物園 競り市 11/15(storeSale.exclude)、Lier.ハウス＆Sakier.直売所 11/15-16・12/26-27・1/17-18(producerHouseMonthly)。ほかの植物系の行は掲載済みか見送り済み。
- LEAFLA 連番 7100〜7135 を確認。右端 7111(増えず)。
- Google 検索は最初の fetch から `a h3` 0件で打ち切り(3日続き)。中止・延期の検索は WebSearch で1回(該当なし)。

## watch-sources 巡回(日曜)
- 保留(revisit=true)の handle 13件、awaitingNextEdition の personal 3件(nagashima_marche / wi_wibotanical / j_n_ishikawa)、personal 13件を組み込みブラウザで巡回。topsearch と web_profile_info は 404 だったがプロフィールのグリッドは読めた。
- 新規掲載: ななヨン グランドオープンイベント(12/12-13 筑前町、@nanayon7_4 Dfqw1fpoNa7。出店者一覧でアガベ・塊根の店が十数組。見送り記録を消した)、FLEX 6th ANNIVERSARY AONOCRAFT Store Event(12/13 掛川、@aonocraft DfqIg-WPQvy。@uchidanouen の投稿で発見)。
- 保留の再評価11件は主催の告知が出ておらず継続(revisitedOn 更新)。

## 日次メールの項目
- time_vs_organizer_post 2件: ボタニックフロントフェス(10:00〜15:00、出典を DfuPNaWhHW6 に、別名フェスタを aliases)、オキボタ December(日別の時刻・入場料・会場 展示ホールD、出典を DfuAKgKAOPx に)。
- rejected_revisit_expired 1件: 花宇宙ドリームガーデン 11/14 を revisit=false。
- 本業後の build-health-mail 予定: 生成物の古さ(index_card_body_drift、daily の再生成で消える)のみ。

## 反映と CI
- push 3回(記録 / events.json と見送り / new-events.json)。sync-events: 2件取り込み、enrich は aggregator 出典で SKIP、値の書き戻しなし。
- プレイブック §3.6 に「topsearch の 404 だけで巡回を打ち切らない」を1行追加。

clone 削除済み。
