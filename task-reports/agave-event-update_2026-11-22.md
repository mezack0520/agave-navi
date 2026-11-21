# agave-event-update 2026-11-22

## 掲載(new-events.json 6件、sync-events で取り込み済み)
- YOSHIMURA CACTUS POP UP STORE in CALEE TOKYO 11/21-23 … 主催 @calee_official DftPAIKvCiz(前日の needs_browser)
- FEEL BEETLE マルシェ 11/23 鹿児島 … 主催 @ryokuwakabu5525 DfhaJfPAUFf(植物ブース9店)
- everybody plants 11/29 沖縄市 … 主催 @everybodymilktea_okinawa Df0uOVqzPJ-
- necomoss ビカクシダ販売会 12/6 プロトリーフゆめが丘 … 主催 @protoleaf.shop_yumegaoka Df9IEMvu8nx
- キムタロウ さくら植物園店 クリスマスイベント 12/19 … 主催 @chanchanchikachanchan Df_jQEKHxYP(外部出店者あり、storeSale.include)
- HOP(ビカクシダ販売会) 12/26-27 オザキフラワーパーク … 主催 @ozakiflowerpark Df9cHG-tIeV

## 既存の回の修正(events.json)
- igashira-park-taniku-saboten-tenjikai-2026-11: 施設の展示会頁が次の展示に替わり開催日を書かなくなった(日次メールの source_page_wrong_edition)。出典を主催 IG の告知 Df3LVr_kw8b に
- nagoriba-maizuru-2026-11: 主催告知 DeHUJ0XE-b8 は4号棟。venue/location/time/説明文を直し、出店者を8組に
- green-days-matsuyama-vol3-2026(needs_browser): venue/mapQuery が vol.4 の会場だった。location と説明文の城山公園に揃えた

## 見送り(rejected-events.json 10件)
味の素スタジアム フリマ、SPIKE GREEN PLANET 柱サボテン大放出、base plantz BLACK FRIDAY、中部広域グリーンフェスタ 植木市、plant_obs フィギュア POP UP、千秋園 花と植物フェア、あまんだ多肉 スマイルハートマルシェ、MENOSYAMA 薪窯の山、青坊主ほか大阪グループ展、boo.ta29 ハウス販売

## Step0
- coverage-gaps: errors 0、gaps 12件を全件処理(掲載4・見送り7・掲載済みの切れた見出し1)
- scan-organizer-posts 約130行を読んだ。新規は上の necomoss・キムタロウ。森の多肉園 BIG/宮崎/鹿児島、花友フェスタ、多肉楽市、多肉だょ福山は掲載済み
- LEAFLA 日付別(11/22〜12/26)から記事を引いた。右端は topics7350
- Google 検索は1本目から `a h3` 0件で打ち切り。中止・延期の検索は未実施
- search-demand 2件(天下一植物界 2027、アガベ ミーティング 2027): 告知なし、--no-change で記録

## watch-sources 巡回(日曜)
- 保留の主催と次回待ちの personal 14件: palette_market_kagawa、tyutyu_ivt、ozco70、nebachi_shop、sumori_634、tante_tano_、nagashima_marche、wi_wibotanical、kumakiri55、fuji_taniku、cosmo_fes_official、j_n_ishikawa、midorino_marche、everybodymilktea_okinawa
- 保留10件は新しい告知なし。revisitedOn を更新
- ナゴリバ舞鶴の会場の誤りはこの巡回で見つけた

## 日次メール項目
- source_page_wrong_edition 1件: fixed
- needs_browser 2件: 片づけ済み(open 0件)

## 気づき
- 主催 IG のグリッドは約45件で読み込みが止まり、数か月前の告知は辿れない。プレイブック §3.6 に1行

clone 削除済み
