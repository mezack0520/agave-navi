# event-monitor 2026-11-25

## 監査
- audit.py: urgent 0。data-integrity-check: errors 0 / warnings 0。build-health-mail: 反映3件(agave-event-update の修正)で send=True。
- 前日比の悪化: organizer_unlisted_dates 1(info)。@protoleaf.shop_futakotamagawa の寄せ植えワークショップ(DgHGogvEVoh、12/1・1/13・1/27)。
- 解消: なし。coverage_gap_stale 1→3 は掲載済みの回で、次の巡回で消える。
- pending-judgments: items 0。needs_browser の未対応 0。

## 直したこと
- 寄せ植えワークショップは同じ講座の見送り protoleaf-futako-yoseue-ws-2026-10 が既にあった。回ごとに見送らず seriesWide にし、投稿を reason に記録。明日の daily で organizer_unlisted_dates から消える(それまで organizer_unlisted_rejected_post に2件)。
- 監査 series_organizer_ig_missing(info)を追加。同じシリーズ(normalize_series_name)の他の回が1つの handle を持つのに organizerIg が無い回。主催の頁(organizer_pages)は organizerIg で束ねるので、その回が実績から漏れていた。
  変更前24件 → organizerIg を入れて0件。url / sourceUrl が別の handle を指す3件(shokubutsu-chudoku-vol2-2026-07、enjoy-place-outside-tsukuba-2026、botanical-botanical-osaka)は主催が別かもしれないので数えず、件数だけ出す。
- プレイブック §3.5 の organizerIg に1行。

## 未対応
- なし
