# site-health-check 2026-11-09

- 構造: トップ・詳細3・ガイド3・calendar・map・about・listing・ikitai・dashboard・sitemap・404 すべて200、canonical/JSON-LD正常
- アフィリエイト: トップ・詳細とも .rk-card 3 / .aff-shop-btn 6(tag=aganavi-22)、agn_rk_v1 あり。.aff-bar は375幅の詳細で表示(flex)。コンソールエラー0
- Actions: 11-02以降 failure 0(cancelled は concurrency のみ)
- audit: urgent 0。upcoming_no_image 71。キュー1件追加
- 修正: 手書き13頁の outbound.js 版数が 20260922b のまま古かった。sync-footers.py と audit.py の版数検査に outbound/nav/top-filter を追加し、13頁を 20261020b に更新
- 週次点検: ①agave-event-update の watch-sources 巡回「未実施」が10-06以降22回。pending-judgments に週1化の提案を積んだ ②eyecatch の日付付き一時フォルダが削除できず10個残存。プレイブック §3.7 を固定名上書きに変更
- clone 削除済み
