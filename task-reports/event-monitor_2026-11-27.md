# event-monitor 2026-11-27

## 監査
- urgent 0。data-integrity-check: errors 0 / warnings 0。
- 前日比の悪化(info): organizer_unlisted_dates 0→2、organizer_unlisted_rejected_post 0→3、image_host_unrelated 0→1。いずれも今朝の agave-event-update の掲載・見送り由来。
- 日次メールの予定: 項目なし(send=False)。

## 直したこと
- organizer_unlisted_dates / organizer_unlisted_rejected_post: 主催の見張りの写し(organizer-posts.json checkedOn)より後に決めた見送りが、両方の検査に翌日まで出ていた。audit.py で、写しより後の見送りが挙げた投稿は対応済みとして数えず、rejected_post は写しより前の見送りだけを数えるようにした。decided を前に倒したデータで 2件 / 3件出ることを確認。
- image_host_unrelated: taniku-popup-aeonmall-kagoshima-bay-2026-11 の画像は出典頁の og:image(image-cdn.aeonmall.jp)。イオンモール各館サイトの自社 CDN を同じ持ち主とみなす規則を audit.py に追加。

## 残り
- pending-judgments: 0件。needs_browser の skipped: 0件。
- task_run_gap / inquiry_review_gap は 2026-11-21 の PC 停止(全タスク同日)。対処不要。

clone 削除済み。
