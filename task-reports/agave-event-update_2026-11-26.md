# agave-event-update 2026-11-26

## 掲載(new-events.json 3件、sync-events で取り込み済み。enrich の書き戻しなし)
- AGAVE DE KANPAI 11/27-29 キトアトリエ(大阪・放出) … coverage_gaps(NextMeet)。主催 @kito_osaka の告知 Df9bc6KgRGG。出店5者のうち植物2者(アガベ、多肉・塊根)で compositeEvents の3割を超える
- 加西Plants Market 植物と雑貨と古いもの 12/6 兵庫県立フラワーセンター駐車場 … 見送り(unverified・revisit)から掲載へ。主催は ここのは(@kokonoha.kasai)と 結の多肉びより(@succulentandflower.yui)、告知 DfWu364Pqd3。見送り記録は削除
- ROOTS MARKET 2027-03-21 稲毛海浜公園 … @vivi_succulent DgHy5sGy57M。10/25 中止回のやり直し

## 見送り(rejected-events.json)
- 大鉢祭り 12/19-20(堺・八六八ビル) … undisclosed・revisit から policy に確定(DgFF5VhOlnU。作家の植木鉢の販売で potteryAndVesselShows)
- 第6回 枚方 蚤の市 11/28-29 … 出店者 @taniten_kengo202 の告知。古道具の蚤の市(compositeEvents)
- BOTANICA LOVE CHRISTMAS 12/19-20 BOTANICA MUSEUM … クリスマス企画の総合マルシェ(compositeEvents)
- ゆくはし植物園 競り市 … 11/29 回も同じ型のため既存記録を seriesWide に

## 日次メール項目
- organizer_cancel_signal: ボタニカルガーデン in ホコテン！(12/13) は誤検知。投稿 De3-bgRk0ev は 10/25 回の中止で、末尾の「次回は12月13日」で鳴った → cancel-reviewed.json に記録
- rejected_revisit_due: 加西PLANTS MARKET → 掲載(上記)
- needs_browser: open 0件

## Step0
- coverage_gaps 1件(AGAVE DE KANPAI)→ 掲載
- scan-organizer-posts 116投稿を読んだ。CI の信号3件: ROOTS MARKET 掲載、枚方蚤の市 見送り、愛珍植祭 1/23 は整理券の前日販売日(コードで対処)
- LEAFLA: event-list の topics7443〜7474(9件)を読んだ。対象内の新出なし。右端 topics7474
- Google 検索3本(多肉 12月、アガベ・塊根 12月、中止・延期 12月)+個別の裏取り。新出は上記のみ
- search-demand 2件 --no-change(DOLCE'S 多肉植物販売会の次回告知なし、まちの駅笠間宿は掲載済み)
- watch-sources 巡回: 日曜のみ
- watch-seeds に @kito_osaka

## 気づき(恒久化)
- ig-organizer-watch.py: 中止の照合から「次回は◯月◯日」の日付を外した(cancel_month_days)
- ig-organizer-watch.py: 「前日販売」「先行販売」の見出しに続く日付を開催日に数えない(_TICKET_DAYSALE_BEFORE)。全投稿で拾う日付は 2950 → 2949(愛珍植祭の 1/23 だけ)
- プレイブック §3.1: LEAFLA の記事番号は飛び番(7432〜7442 が404で 7443 が存在)。連番で止めず event-list の番号を拾う手順に書き換え

clone 削除済み
