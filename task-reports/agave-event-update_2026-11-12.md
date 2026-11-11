# agave-event-update 2026-11-12

- 起動記録: task-runs.json に記録・push 済み
- needs_browser の引き継ぎ: 0件
- Step0: coverage-gaps 6件(errors 0)を一次情報で処理。掲載2・見送り4
- Google 検索(qdr:w2 ほか)15本: 新規候補 GREENS vol.5(見送り)、THE TANIKU EXPO(主催未特定で保留)
- scan-organizer-posts 173行: 主催の告知から掲載7件、見送り記録3件

## 掲載 10件
- 植フェス GLOBAL PLANTS MARKET(ジョイフル本田千葉NT 11/14-15) 店舗イベント頁 id=45641・出店者一覧画像
- 世界樹の雫 大宮マルイ(11/13-15) @sekaijunosizuku DfmoRD1ADpX
- ボタらいふ Euphorbia Fair(焼津 11/14-17) @botalife_pachy DfjgjnJn3GU
- Heartplants.×KASUGADOU(豊中 11/22) @heart_plants DfmPJaatm31(保留から掲載)
- BACK TO THE FOREST vol.2(uju 大阪 12/20) @backplain77 DfjpffSk77d
- Lier.多肉フェスティバル 市川 11/21・所沢 12/26・名取 12/27 @lier_succulent DfndnU4Ev26
- 森の多肉園販売会 宮崎 12/12・鹿児島 12/13 @morinotanikuen DfZWuCCHwh_
- sync-events の enrich は10件とも値を書き換えていない

## 見送り
- policy: あいち花マルシェ三河 / 香りの植物学 / フェルム・ド・ノエル Vol.31 / GREENS vol.5 / グリーンフェス大分 / かぐらばマルシェ
- unverified(revisit): sumori Open garden 冬 12/19(出店者告知のみ) / THE TANIKU EXPO 12/12 大さん橋(主催未特定)
- 保留継続: ヒナタ多肉園 11/22(revisitedOn 更新)

## 日次メール項目
- rejected_revisit_due 2件: 処理済み
- 中止兆候の空振り(井頭公園 多肉植物とサボテンの展示会): check-cancelled.py に repeated_block を追加。同じ class の入れ物で催しを並べる一覧頁は、その回の入れ物に署名を絞る。実頁で sigScope=article・128字を確認、self-test 通過

## 未対応
- なし

clone 削除済み
