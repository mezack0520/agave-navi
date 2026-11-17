# agave-event-update 2026-11-18 (水)

- 日次メール予定の項目: time_vs_organizer_post 1件、rejected_revisit_due 2件、coverage_gaps 1件 → すべて処理。
- RARE PLANTS COLLECTION: 主催告知 DfCGCHsyLSh で time 10:00〜20:00・入場無料、sourceUrl を同投稿に。
- coverage_gaps P•A•F〜Plant addict Festa は掲載済み。NextMeet が「広島県佐伯区」と区だけ書くため場所の照合で外れていた → coverage-sweep の place_ok を政令市の区で当たるよう修正、self-test 追加。45日の再照合で取りこぼし0。
- 再評価: 鼓動 vol.5 は出店者一覧が出て植物専門店6組(includeIf 専門店3者以上)→ 掲載。bizarre Park LOCAL MARKET 11月回は内訳非公開のまま → 見送り確定(revisit=false)。
- 新規(new-events.json): 鼓動 vol.5 (11/28-29 松江) / 多肉園おひさま アイシティ21 (11/28-29 長野・山形村) / THE BOTANICAL SHOW 海老名駅西口 (2027-04-03〜04)。
- Step0: scan-organizer-posts 137行を読んだ。LEAFLA 連番 7108〜7121、右端 7111(増えず)。Google 検索は最初の fetch から `a h3` 0件で打ち切り。中止・延期の検索は該当なし。truncatedUnresolved 5件はいずれも掲載済みか見送り済み。
- search-demand: botajam / ぶらりぷらんつ / BOTANICAL BOTANICAL 大阪 の次回告知なし(--no-change で記録)。
- watch-sources 巡回は平日のため対象外。
