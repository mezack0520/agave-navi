# event-monitor 2026-11-17

## 監査
- audit.py: 悪化 time_vs_organizer_post 0→1。data-integrity-check: errors 0 / warnings 0(805件)。
- 悪化の原因は直近の掲載(agave-event-update 41f32b74 の kanaoka-midori-marche-2026-11)。値は主催の最新告知 Dfn7Q9GzebC(平日 9:00〜15:00、土日 9:00〜16:00)どおりで正しい。
- 出典 De5creYzXjg は【金岡みどりのマルシェ】の節に時刻が無く、下の節に靱公園植木市 9時〜17時・甲子園口バル&マルシェ 10:00〜17:00 を並べる。監査がこれを回の時刻と読んだ誤検知。

## 監査の拡張
- `sitelib.event_section`: 見出し(【名前】・絵文字で挟んだ「名前」)が2つ以上ある投稿は、回の名前の見出しから次の見出しか区切り行までだけを読む。time_vs_organizer_post に適用、自己テスト `_self_test_event_section` を監査から毎回呼ぶ。
- organizer-posts.json の直近40版に当てた: 鳴り方が変わったのは kanaoka の1件だけ(鳴る→鳴らない)。他に読む時刻が変わった2件(plant-guild-popup-vol5-fukuchiyama-2026-11、toyama-saboten-taniku-9th-2026-10)は前後とも鳴らない。
- プレイブック §3.4 に場所を1行足した。

## 日次メールの項目
- 直せず残る項目: 0(上の1件を log-fix に fixed で記録)。
- 判断待ち: site-health-check:gsc-secret の1件(目崎のアカウントでしかできない設定。継続)。
- pending-judgments の解消済み: なし。

## 合図
- mail-request.json を push。
