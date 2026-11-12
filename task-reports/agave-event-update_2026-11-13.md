# agave-event-update 2026-11-13 (金)

## Step0 カバレッジ
- coverage-gaps 5件(errors 0)を処理。
  - 掲載: 第6回 Life with botanical(11/15 群馬館林、主催 J.S.P.S. の @ssd_keydw DejcDBEzGfL)、田主丸ガーデン植物販売会 Vol.5(11/21-22 福岡久留米、出店者が開く合同販売会 @bizmackie1115 DfljJVtBj2E)。
  - 見送り: 「解像度のあがる、多年草の見方」(講座・対象外ジャンル)、「多肉植物寄植えの会」(12/11、ワークショップ単独)。LEAFLA 見出しの「寄植え」表記が OUT_OF_SCOPE の「寄せ植え」をすり抜けていたので、coverage-sweep.py に '寄植え' '多年草' を足した。
- scan-organizer-posts 一覧を通読。新規掲載: はなみちるさんの多肉販売会(11/14-15 ジョイフルエーケー帯広店、主催告知 Dfl91AdTdi_)。他の候補(多肉Revolution、多肉だょ!全員集合 津山/福山、植祭、サンタフェ、ゆるっと多肉マルシェ等)は掲載済み。ゆくはし植物園 競り市 11/15 は前回と同じ storeSale で対象外。
- Google 検索は最初の1回のあとリダイレクト頁が続き、navigate し直しても戻らなかったので打ち切り。中止・延期の検索は WebSearch で1回(該当なし)。
- watch-sources 巡回は日曜のみ(本日対象外)。

## 日次メールの項目
- time_vs_organizer_post 2件: 森の多肉園販売会 in 宮崎 / in 鹿児島 に主催告知 DfpDvpun4iI の 10:30〜14:00 を入れ、出典を同投稿に差し替え。説明文の「時間未告知」の文を消し、鹿児島の location から区画(展示室)を外した。
- 本業後の build-health-mail 予定: 上記以外の項目なし。

## 反映と CI
- sync-events: 3件 OK、enrich は出典が無関係頁・アグリゲータのため SKIP-ALL(値の書き戻しなし)。
- プレイブック §2 に「events.json の push は daily を起こす。続けて new-events を押すなら待つ」を追記(本日 daily 実行中に new-events を押した。sync-events は成功)。

clone 削除済み。
