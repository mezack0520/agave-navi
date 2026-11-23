# event-monitor 2026-11-24

## 監査
- audit.py: urgent 0。data-integrity-check: errors 0 / warnings 0。build-health-mail: 送る項目なし(send=False)。
- 前日比の悪化: organizer_unlisted_dates 3 / organizer_unlisted_rejected_post 5(info)。3件とも agave-event-update が今朝 daily の後に見送りを記録した投稿(DgBnfDxhubp, DgEd9OCAOM0, DfwFb6EzXvP)。ig-organizer-watch.known_elsewhere に今のデータで当てて全日付 True を確認。明日の daily で消える。
- 解消: coverage_gap_stale 1→0。
- task_run_gap: 11/21 に event-listing-review・agave-event-update・agave-navi-eyecatch が抜け(過去分、info)。
- pending-judgments: items 0。needs_browser の未対応 0。

## 直したこと
- index 対象(3件以上)のタグ頁3つがハッシュの URL のまま公開されていた(ポップアップ 4件、ビザールプランツ 6件、観葉植物 6件)。
  sitelib.TAG_ROMAJI に popup / bizarre / houseplant を足し、旧 slug は TAG_SLUG_REDIRECTS から中継頁(noindex + canonical + refresh)を生成。
- 監査 tag_slug_romaji_candidates(info)を追加。変更前のデータで3件、変更後0件を確認。閾値は sitelib.LANDING_INDEX_MIN に寄せ、generate-landing-pages の THIN_THRESHOLD もそれを読む。
- プレイブック §3.5 に1行。

## 未対応
- なし

clone 削除済み
