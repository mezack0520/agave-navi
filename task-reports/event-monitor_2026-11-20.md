# event-monitor 2026-11-20

- 監査: urgent 0、info 1(rejected_revisit_stale: monster-plants-kagawa-2027-03。前日 2 → 1 で解消方向、悪化なし)。data-integrity-check: errors 0 / warnings 0。
- 日次メール予定: 反映1件(gamagori-taniku-festa-hamamatsu-2nd-2027-01 の time)。直す残りなし。pending-judgments は空、needs_browser の積み残しなし。
- 監査の拡張: `venue_location_disagree` が地名を共有する別施設(松山中央公園 / 松山城山公園)を素通りしていた。location の施設名と venue が互いを含まない回も数えるよう直した。全815件に当てて green-days-matsuyama-vol3-2026 の1件のみ(誤検知0)。
- 未対応: green-days-matsuyama-vol3-2026 の会場は出典で確定できず、`log-fix --kind needs_browser` で agave-event-update に渡した。
- mail-request.json を push(日次メールの合図)。clone 削除済み。
