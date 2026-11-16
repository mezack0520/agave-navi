# agave-event-update 2026-11-17 (火)

## Step0 カバレッジ
- coverage-gaps 2件(errors 0)。金岡みどりのマルシェ 11/25-30(@yokoen_tk De5creYzXjg)、ひだかさんげ 11/29(@hidaka_sange DfuSAckJ26s)を掲載。
- scan-organizer-posts 119行を通読。掲載: タニックリ 12/13(@shikokuzouen)、麋祭 vol.02 2027-04-11(@b.g_ozman)、cham_plants 植物販売会 12/19 二子玉川・12/20 ゆめが丘(@protoleaf.shop_futakotamagawa)、がまごおり多肉フェスタ 第2回 in 浜松 2027-01-31 と第7回 蒲郡 2027-03-13〜14(@gamagori_taniku_festa Dfx2qUGTZeS)。ほかの植物系の行は掲載済み・見送り済みかワークショップ単独。
- truncatedUnresolved: fiore soffitta POP UP(LEAFLA topics7106、生花)を見送り記録。
- LEAFLA 連番 7100〜7125 を確認。右端 7111(増えず)。
- Google 検索は最初の fetch から `a h3` 0件で打ち切り。WebSearch 3本(ひだかさんげ / 多肉楽市 高鍋 / 中止・延期 12月)は該当なし。
- watch-sources 巡回は日曜のみ。

## 日次メールの項目
- 送る予定の項目は要判断1件(GSC_SA_KEY)のみ。info を処理した。
- organizer_unlisted_dates(蒲郡 1/31): 上の2件の掲載で解消。保留 gamagori-taniku-festa-7th-2027-03 は日付確定で記録を消した。
- rejected_revisit_stale: 3件を見た(蒲郡第7回=掲載、COSMOフェス第3回・大鉢祭り=継続)。
- cancel_suspects 3件: すべて開催予定のまま(本文の追記)。八王子は3回目になるため記録せず、check-cancelled.py に grown_only を足した(プレイブック §3.8 に1行)。
- 金岡の time_vs_organizer_post: CI の organizer-posts.json が本文を800字で切っていた(3867件中450件)。ig-organizer-watch.py を2200字にした。次の daily で消える。skipped で記録。

## 反映
- push 2回(記録 / 新規8件・見送り・コード)。sync-events 成功、新規の値の書き戻しなし。
