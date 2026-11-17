# event-monitor 2026-11-18

## 監査
- audit.py: 悪化なし。解消 coverage_gap_stale 2→0。urgent 0。data-integrity-check: errors 0 / warnings 0(808件)。
- info に organizer_unlisted_dates 1件(@gunmacactusclub 11-22 群馬第4交換会 11月場所 DfvdPc7z-8y)。見送り gunma-dai4-koukankai-2026-09 は 11-16 に seriesWide にしてあるが、主催の見張りが見送りを日付で引くため当たっていなかった。

## 監査の拡張
- `ig-organizer-watch.day_indexes` / `known_elsewhere`: seriesWide の見送りを日付で絞らずに名前と aliases で当てる。scan-organizer-posts も同じ関数を使う。自己テストに2件足した。
- scan-organizer-posts を直す前後で比べた: 消えたのは上の1行だけ(144→143投稿、CI の信号の対象 1→0)。
- `organizer_unlisted_rejected_post`(info)に、seriesWide の見送りの名前が出る投稿が候補に残っている型を足した。直す前の organizer-posts.json で狙いの1件が出る。次の daily で0になる。
- プレイブック §3.3 の seriesWide の行に、見張りも日付で絞らないことを書いた。

## 日次メールの項目
- build-health-mail.py: 反映8件(朝のタスクの分)、直せず残る項目 0、判断待ち 0。
- pending-judgments: items 0。解消済みの消し込みなし。

## 合図
- mail-request.json を push。clone 削除済み。
