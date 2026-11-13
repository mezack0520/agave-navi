# agave-event-update 2026-11-14 (土)

## Step0 カバレッジ
- coverage-gaps 5件(errors 0)を処理。すべて主催の一次情報で裏取りして掲載。
  - kijimuna × BOTANY 植物販売会(11/29 和歌山 丸十家具、@ki_ji_muna Dfo0AJSItWA)。LEAFLA の見出し「BOTAJAM」は 11/7 岐阜の別催しの名前で誤り。LEAFLA 名は aliases。
  - 珍奇植物市場 Vol.10(12/5-6 沖縄 メイクマン ニューマン店、@tanikunchu DfrUHCBhRtI)。
  - PIECE POP UP PLANTS MARKET(12/6 松山 美容室 sika、@pepe__green DfR1zcVziXG)。
  - 日本ブロメリア協会「総会」(12/6 西新宿、bromeliads.jp news-13496)。同協会サイトから未掲載の BSJミーティング大阪(11/23)も掲載。
  - 黒★多肉 presents マルシェ001(2027/1/16 真岡、@nyanko.and.taniku DfmZav1n8VB。10組中植物4組)。
- scan-organizer-posts 通読。新規掲載: Tick-Tick vol.2(11/22 四国造園、@shikokuzouen DfrYziGBGSj)、CPG#4(2027/4/24-25 フラリエ、@campparkworld Dfl5EqQAeLx)。見送り: 2026 Winter Fes in植物園(富山・鉢花と食品のマルシェ)、私へ贈るご褒美マルシェ(PLANTS2306 津店・植物の出店者なし)。
- truncatedUnresolved: ONEDAY.factory® POP UP は掲載済みの URBAN JUNGLE WEEKS(阪急うめだ GREEN AGE)の中の企画なので aliases に足した。新風会盆栽まつり(盆栽)は見送りに記録。
- LEAFLA 連番 7040〜7121 を確認。右端 7111。
- Google 検索は最初から空の頁で打ち切り(2日続き。プレイブック §3.1 に代替を追記)。中止・延期の検索は WebSearch で1回(該当なし)。
- watch-sources 巡回は日曜のみ(本日対象外)。

## 日次メールの項目
- cancel_review_repeated 1件(井頭公園 多肉植物とサボテンの展示会): 3回の空振りは 11-12 に署名を回の枠に絞る前のもの。今日の変化は枠の摘要に最終日の時刻が足された本物の変化で、中止ではない。check-cancelled.py に scopeSince(範囲・作り方を変えた日)を足し、audit はそれより前の記録を数えないよう直した。cancel-watch.json の該当1件に 11-12 を入れた。
- 本業後の build-health-mail 予定: 取り込み待ち以外の項目なし。

## 反映と CI
- sync-events: 8件取り込み済み、値の書き戻しなし。
- 気づき: agavista-vol2-matsuyama-2026-06(終了済み)の url が無関係の企業頁(jpn.sika.com)。会場は今回の PIECE と同じ美容室 sika の可能性が高いが、主催未特定のため未修正。

clone 削除済み。
