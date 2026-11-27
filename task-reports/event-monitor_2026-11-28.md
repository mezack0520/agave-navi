# event-monitor 2026-11-28

## 監査
- 悪化: venue_key_split 0→1(沖縄 ESTINATEHOTEL / ESTINATEHOTELNAHA)。原因は本日掲載の bikaku-shokubutsu-sagyoshitsu-naha-2026-12 が既存の must-buy-market-okinawa-2026-05 と別表記だったこと。
- data-integrity-check: errors 0 / warnings 0。
- 修正後の手元監査で悪化なし(検出 809→807)。

## 直したこと
- must-buy-market-okinawa-2026-05: location を「ESTINATE HOTEL NAHA（沖縄県那覇市松山2丁目3-11）」に揃え、mapQuery を追加、updatedAt を今日に。
- botanical-monsters-2027-okazaki(cancel_suspects): 公式は 2027/1/17 のまま。中止の語は荒天中止の条件文だけ。cancel-reviewed.json に記録。
- 日次メールの「残っていること」は上の1件で、解消。

## 恒久化
- merge-new-events.py: 載せた回が既存の会場と割れたら `VENUE-SPLIT:` を出す(判定は sitelib.venue_split_groups、監査と同じ)。修正前のデータで1組、修正後0組、無関係な回で0組を確認。
- プレイブック §3.2 に1行。

## 未対応
- なし

## 合図
- request-run.py mail を push に含めた。

clone 削除済み
