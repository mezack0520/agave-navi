# agave-event-update 2026-11-24

## 掲載(new-events.json 3件、sync-events で取り込み済み)
- 緑楽宴mini in 明石 2027-05-02 明石市民広場 … 主催 @honoka.kakogawa DgEd9OCAOM0
- 園日 Vol.19 2027-03-14(tbd)… 主催 @banksia.111 DgD-L__IX6_「次は春 3月14日の予定」
- THE TANIKU EXPO 12/12 大さん橋ホール … 出店者 @botan.29 Df1Yi7UB2aZ が @lier_succulent 主催と明記、主催の予定表 DfndnU4Ev26。保留(rejected revisit)を解除

## 見送り(rejected-events.json 12件)
- policy: フラワーオークション11/28(seriesWide)、時の輪郭 PROLOGUE 11/28(50名抽選の公演)、SUMORISU タニクリスマス会(要予約・満席)、GREEN AGE CHRISTMAS MARKET、HAPPA SAN の BGM 公開、edamame 園芸店の出店2件
- undisclosed: ビカ森ハウス 12/13(所在地非公開で3回目、seriesWide)
- unverified・revisit: はみもろ12/13・しょくちゅうしょくぶつ vol.3(どちらも出店者 @honoka.kakogawa の予定表のみ)、タニトピア序章 12/27(生産者の告知のみ、主催アカウント不明)、らはちゅうクリスマス 12/13(日付と名前だけ)
- 確定: HAMACHO MIDORI MARKET(開催10日前に出展者6組を再確認、revisit=false)

## Step0
- coverage-gaps: errors 0、gaps 0。truncatedUnresolved 4件はタニトピア(見送り)と対象外3件
- scan-organizer-posts 114行を読んだ。新規は上の緑楽宴mini・園日、見送りは上のとおり
- LEAFLA 連番 topics7391〜7455。200 は 7393・7401・7404・7405・7410・7415・7423・7428・7429・7431、右端 topics7431
- Google: タブからの fetch は JS 必須のリダイレクト頁しか返さず0件(3日目)。navigate すれば読めたので4本検索(中止・延期の検索を含む)。プレイブック §3.1 を書き換えた
- search-demand 2件: 緑楽宴(次の回を掲載、--change)、モロモロプランツ(第20回の告知なし、--no-change)
- watch-sources 巡回: 平日のため対象外

## 日次メール項目
- organizer_cancel_signal: KKT多肉FES vol.6 の「開催を見送」は福引の話で開催予定のまま。cancel-reviewed に記録
- rejected_revisit_due: HAMACHO MIDORI MARKET を見送り確定
- needs_browser: open 0件

## 気づき(恒久化)
- check-cancelled.py の SUBPROGRAM_CANCEL に福引・抽選・ガチャと「見送」を足した(self-test 2件追加、ig-organizer-watch の self-test も OK)
- プレイブック §3.1 の Google 検索を navigate 方式に改めた

clone 削除済み
