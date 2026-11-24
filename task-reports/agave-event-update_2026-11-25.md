# agave-event-update 2026-11-25

## 掲載(new-events.json 3件、sync-events で取り込み済み)
- ボタニカルガーデン in ホコテン！ 2026 12/13 西川緑道公園筋(岡山) … 主催の岡山市公式頁 kankou/0000007281 と岡山観光WEBの出店者一覧。多肉の店が多く compositeEvents の閾値を超える
- BOTANICAL LOVER(ボタラバ) 12/13 高田馬場 … 主催 @felicita_plants の Threads DgHkNrYkZ-1。8ショップ
- オキボタ with ハチクラ祭 in 岡山 2027 2/27-28 コンベックス岡山 … 主催公式サイト

## 既存の回の修正(events.json)
- 鼓動 vol.5 11/28 → postponed(主催 @kodo_haru DgH7S6VT6aL、天候、延期後の日程は未発表)
- NBgardenフェスタ 12/20 → 会場 SBS の告知で名称「週末ボタニカル」を aliases、time 10:00〜15:00、説明文と出典を更新
- PLANT AND POT vol.15 の location から「1階」を外し、BOTANICAL LOVER と同じ会場に束ねた

## 見送り(rejected-events.json 8件)
- policy: FUJIYAMA DAYS 冬(グルメ・犬の総合フェス)、SEEDLING LABORATORY 値引きセール、日本多肉植物の会 本部新年大会、植物を愛でる店主の集い(花苗が主題)、トハメルカド第16回(第15回と同じ)、世界らん展2027(seriesWide)
- undisclosed・revisit: Yubisakino Jyunin 冬のイベント 12/19〜(内容は店頭のみ)
- unverified・revisit: BOTANICAL BOTANICAL GIFU 2027-04-10(PUKUBOOK のみ)

## Step0
- coverage_gaps 8件を全件処理(掲載3・見送り4・照合の修正1)
- scan-organizer-posts 101投稿を読んだ。新規なし、見送り2件は上記
- Google 検索7本+個別の裏取り8本。主な新出は上の掲載・見送りのとおり。花伝多肉祭り2026(11/21-22、久留米)は終了後に発見 → watch-seeds に @hanaden.k
- LEAFLA 連番 topics7432〜7441 は全て404。右端は topics7431 のまま
- search-demand 1件: よってって南紀の台(次の回 12/6 掲載済み、--no-change)
- watch-sources 巡回: 平日のため対象外

## 日次メール項目
- organizer_cancel_signal: 鼓動 vol.5 を延期に
- time_vs_organizer_post: 金岡みどりのマルシェは誤検知(別の節の珍奇植物フェアの時刻)
- needs_browser: open 0件

## 気づき(恒久化)
- sitelib.organizer_post_hours_missing が event_section で回の節だけを読むように(_self_test_event_section に実データのケースを追加、直す前のコードで NG になることを確認)
- coverage-sweep.judge: アグリゲータの県が誤っていても「県 / 会場」の会場名が location に出る回は当てる(self-test 追加)

clone 削除済み
