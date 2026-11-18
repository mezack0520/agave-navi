# event-monitor 2026-11-19

## 監査
- urgent 0件(前回も0)。悪化・解消なし。data-integrity-check: errors 0 / warnings 0。
- info: coverage_gaps 1、cancel_suspects 2、rejected_revisit_stale 2。

## 直したこと
- cancel_suspects 2件(bsj-meeting-osaka-2026-11、bsj-soukai-nishishinjuku-2026-12): 公式頁を取得。会期・会場のままで中止・延期の語なし。
  本文 -2字は同日に同じサイトの2頁で起きた共通枠の揺れ。cancel-reviewed.json と auto-fix-log(reviewed)に記録。
- coverage_gaps 1件(HAMACHO MIDORI MARKET 12/04): agave-event-update が今朝見送り済み。巡回時点の写しに残っていただけ。

## 監査・規則の拡張
- check-cancelled.py: 本文の変化を数えない判定を `body_change_benign` に切り出し、本文だけが20字か2%以内で減った変化(開催日あり・中止の語なし)も数えないようにした。
  10月以降 -1% 前後の空振りが7回以上 cancel-reviewed に記録されていた型。self-test に7件追加、全通過。
- audit.py: 取りこぼし候補のうち巡回の後に見送りを記録した回も coverage_gap_stale に分ける(従来は掲載済みだけ)。
- プレイブック §3.1・§3.8 を上の2点に合わせて更新。

## 判断待ち
- pending-judgments: 0件。

## メール
- request-run.py mail で mail-request.json を push(反映2件の予定)。

clone 削除済み
