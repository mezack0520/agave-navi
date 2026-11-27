# agave-event-update 2026-11-28(土)

## 掲載(new-events.json → sync-events 成功、値の書き戻しなし)
- 麋角植物作業室 TOUR 2026 沖縄 2026-12-12〜13 ESTINATE HOTEL NAHA。coverage_gaps(LEAFLA)。主催 @pine.field.garage Dft0hwGFMte / @tompots_501 DgMquNXyY-G
- TANICHU × Green Heads Nursery 草納め忘年会 2026-12-20 シマムラ園芸 第2ハウス。Google 検索で発見(LEAFLA topics7290)。主催 @toningogo Df9Tfw5zqWz

## 既存の回の修正(events.json)
- roots-plus-vol2-2027-03: 主催 DgPB113lJ2R の会場決定で time 10:00〜16:00、天王川公園、confirmed、出典差し替え(日次メールの time_vs_organizer_post)

## 見送り(rejected-events.json)
- AMONG PLANTS(吹上ユニゾン、compositeEvents)/ 関根京子展覧会(作品展、truncatedUnresolved を解決)
- トクとく市(プロトリーフ二子玉川、storeSale)/ edamame園芸 ベーグル出店日
- 宮嶋園芸・lagurus 販売会 2027-01-10 薩摩川内(unverified・revisit。告知が個人アカウントのみ)

## Step0
- coverage-sweep: errors 0、候補2件 → 掲載1・見送り1
- scan-organizer-posts 125件を目視。上記以外は営業案内・WS・出店告知・掲載済み
- Google 検索 10本(2週間)。新規は 草納め忘年会・宮嶋園芸の2件。中止・延期の検索で該当なし
- search-demand 2件 no-change で記録
- watch-seeds に toningogo を追加
- watch-sources 巡回: 土曜のため対象外

## 日次メール
- build-health-mail: urgent 1件(Roots plus の time)→ 修正済み。needs_browser の未処理 0件

clone 削除済み
